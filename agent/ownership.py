"""
Thread Ownership Module with PostgreSQL Persistence

This module demonstrates how a CONSUMER of the copilotkit-langgraph-history library
would implement thread ownership. The library itself remains agnostic to ownership.

Key points:
- This is NOT part of the library - it's in the example only
- Consumers can implement ownership however they want
- Uses PostgreSQL for persistence (same DB as checkpoints)
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import asyncpg


# Global connection pool (set during lifespan)
_pool: Optional[asyncpg.Pool] = None


def set_db_pool(pool: asyncpg.Pool):
    """Set the database connection pool."""
    global _pool
    _pool = pool


def get_db_pool() -> asyncpg.Pool:
    """Get the database connection pool."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized")
    return _pool


# DDL for thread ownership table
OWNERSHIP_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS thread_ownership (
    thread_id    VARCHAR(255) PRIMARY KEY,
    user_id      VARCHAR(255) NOT NULL,
    title        VARCHAR(255),
    created_at   TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_thread_ownership_user 
ON thread_ownership(user_id, created_at DESC);
"""


async def setup_ownership_table(pool: asyncpg.Pool):
    """
    Create the thread_ownership table if it doesn't exist.
    
    Call this during application startup.
    """
    async with pool.acquire() as conn:
        await conn.execute(OWNERSHIP_TABLE_DDL)
    print("✅ Thread ownership table ready!")


class ThreadInfo(BaseModel):
    """Thread information with ownership."""
    thread_id: str
    user_id: str
    title: Optional[str] = None
    created_at: str


class CreateThreadRequest(BaseModel):
    """Request to create a new thread."""
    thread_id: str
    title: Optional[str] = None


class CreateThreadResponse(BaseModel):
    """Response after creating a thread."""
    thread_id: str
    user_id: str
    title: Optional[str]
    created_at: str


def create_ownership_router() -> APIRouter:
    """
    Create the ownership router with user-specific endpoints.
    
    This demonstrates how consumers would layer ownership
    on TOP of the library endpoints.
    """
    router = APIRouter(tags=["Ownership"])
    
    @router.get("/users/{user_id}/threads", response_model=list[ThreadInfo])
    async def list_user_threads(user_id: str):
        """
        List all threads owned by a user.
        
        This is the key endpoint that enables thread persistence
        across different browsers/devices for the same user.
        """
        pool = get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT thread_id, user_id, title, created_at
                FROM thread_ownership
                WHERE user_id = $1
                ORDER BY created_at DESC
                """,
                user_id
            )
            return [
                ThreadInfo(
                    thread_id=row["thread_id"],
                    user_id=row["user_id"],
                    title=row["title"],
                    created_at=row["created_at"].isoformat() if row["created_at"] else None,
                )
                for row in rows
            ]
    
    @router.post("/users/{user_id}/threads", response_model=CreateThreadResponse)
    async def create_user_thread(user_id: str, request: CreateThreadRequest):
        """
        Create a new thread owned by a user.
        
        This registers ownership of a thread before any messages are sent.
        """
        pool = get_db_pool()
        thread_id = request.thread_id
        title = request.title or f"Thread {thread_id[:8]}..."
        
        async with pool.acquire() as conn:
            # Check if thread already exists
            existing = await conn.fetchrow(
                "SELECT thread_id, user_id, title, created_at FROM thread_ownership WHERE thread_id = $1",
                thread_id
            )
            
            if existing:
                if existing["user_id"] != user_id:
                    raise HTTPException(
                        status_code=403,
                        detail="Thread already owned by another user"
                    )
                # Return existing thread info
                return CreateThreadResponse(
                    thread_id=existing["thread_id"],
                    user_id=existing["user_id"],
                    title=existing["title"],
                    created_at=existing["created_at"].isoformat(),
                )
            
            # Create new thread ownership
            now = datetime.utcnow()
            await conn.execute(
                """
                INSERT INTO thread_ownership (thread_id, user_id, title, created_at)
                VALUES ($1, $2, $3, $4)
                """,
                thread_id, user_id, title, now
            )
            
            return CreateThreadResponse(
                thread_id=thread_id,
                user_id=user_id,
                title=title,
                created_at=now.isoformat(),
            )
    
    @router.delete("/users/{user_id}/threads/{thread_id}")
    async def delete_user_thread(user_id: str, thread_id: str):
        """
        Delete a thread (ownership record only).
        
        This removes the ownership record but does NOT delete
        the actual checkpoint data from PostgreSQL.
        """
        pool = get_db_pool()
        async with pool.acquire() as conn:
            # Check ownership first
            existing = await conn.fetchrow(
                "SELECT user_id FROM thread_ownership WHERE thread_id = $1",
                thread_id
            )
            
            if not existing:
                raise HTTPException(status_code=404, detail="Thread not found")
            
            if existing["user_id"] != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="Cannot delete thread owned by another user"
                )
            
            await conn.execute(
                "DELETE FROM thread_ownership WHERE thread_id = $1",
                thread_id
            )
            
            return {"status": "deleted", "thread_id": thread_id}
    
    @router.get("/threads/{thread_id}/owner")
    async def get_thread_owner(thread_id: str):
        """
        Get the owner of a thread.
        
        Useful for verifying ownership before accessing thread data.
        """
        pool = get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT user_id FROM thread_ownership WHERE thread_id = $1",
                thread_id
            )
            
            if not row:
                return {"thread_id": thread_id, "owner": None}
            
            return {"thread_id": thread_id, "owner": row["user_id"]}
    
    @router.patch("/users/{user_id}/threads/{thread_id}")
    async def update_thread_title(user_id: str, thread_id: str, title: str):
        """
        Update a thread's title.
        """
        pool = get_db_pool()
        async with pool.acquire() as conn:
            # Check ownership first
            existing = await conn.fetchrow(
                "SELECT user_id, title, created_at FROM thread_ownership WHERE thread_id = $1",
                thread_id
            )
            
            if not existing:
                raise HTTPException(status_code=404, detail="Thread not found")
            
            if existing["user_id"] != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="Cannot update thread owned by another user"
                )
            
            await conn.execute(
                "UPDATE thread_ownership SET title = $1 WHERE thread_id = $2",
                title, thread_id
            )
            
            return ThreadInfo(
                thread_id=thread_id,
                user_id=user_id,
                title=title,
                created_at=existing["created_at"].isoformat(),
            )
    
    return router


async def verify_thread_ownership(user_id: str, thread_id: str) -> bool:
    """
    Verify that a user owns a thread.
    
    Consumers can use this to wrap library endpoints with ownership checks.
    
    Example usage:
        @app.get("/threads/{thread_id}/history")
        async def get_history_with_auth(thread_id: str, user: User = Depends(get_current_user)):
            if not await verify_thread_ownership(user.id, thread_id):
                raise HTTPException(403, "Not your thread")
            # Now call the library endpoint
            return await library_get_history(thread_id)
    """
    pool = get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT user_id FROM thread_ownership WHERE thread_id = $1",
            thread_id
        )
        
        if not row:
            # Thread not registered - could be a new thread or legacy
            return True  # Allow access (consumer can make this stricter)
        
        return row["user_id"] == user_id
