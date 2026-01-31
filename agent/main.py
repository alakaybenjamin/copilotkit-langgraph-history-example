"""
FastAPI Agent with CopilotKit History Persistence

This example demonstrates:
1. A LangGraph agent served via FastAPI
2. PostgreSQL-backed checkpoint persistence (using CopilotKit's recommended pattern)
3. History endpoints for the copilotkit-langgraph-history TypeScript package
"""

import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

# Add the parent python package to the path for local development
python_pkg_path = Path(__file__).parent.parent.parent.parent / "python" / "src"
if python_pkg_path.exists():
    sys.path.insert(0, str(python_pkg_path))

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import asyncpg
from copilotkit import LangGraphAGUIAgent
from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# Import our history endpoints
from copilotkit_history import add_history_endpoints

# Import the agent workflow
from agent import create_workflow

# Import ownership module (consumer-side implementation, NOT part of the library)
from ownership import create_ownership_router, set_db_pool, setup_ownership_table

# Load environment variables
load_dotenv()

# Validate required environment variables
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY environment variable is required")

if not os.getenv("DATABASE_URL"):
    raise ValueError("DATABASE_URL environment variable is required")

# Get database URL
DATABASE_URL = os.getenv("DATABASE_URL")

# Global reference to the compiled graph (set in lifespan)
graph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    
    This is the recommended pattern from CopilotKit for using AsyncPostgresSaver.
    The checkpointer connection is properly managed within this context.
    """
    global graph
    
    print("🔧 Setting up PostgreSQL connections...")
    
    # Create a connection pool for ownership table
    # (separate from checkpointer to demonstrate consumer pattern)
    ownership_pool = await asyncpg.create_pool(DATABASE_URL)
    set_db_pool(ownership_pool)
    
    # Setup the ownership table (consumer's responsibility)
    await setup_ownership_table(ownership_pool)
    
    async with AsyncPostgresSaver.from_conn_string(DATABASE_URL) as checkpointer:
        # Setup creates the required tables if they don't exist
        await checkpointer.setup()
        print("✅ Checkpointer tables ready!")
        
        # Create the workflow and compile with checkpointer
        workflow = create_workflow()
        graph = workflow.compile(checkpointer=checkpointer)
        print("✅ Graph compiled with PostgreSQL persistence!")
        
        # Add the AG-UI endpoint for CopilotKit
        add_langgraph_fastapi_endpoint(
            app=app,
            agent=LangGraphAGUIAgent(
                name="history_agent",
                description="An agent with persistent thread history support.",
                graph=graph,
            ),
            path="/",
        )
        print("✅ AG-UI endpoint registered!")
        
        # Add history endpoints for thread persistence
        # This is the key integration with copilotkit-langgraph-history!
        add_history_endpoints(app, graph)
        print("✅ History endpoints registered!")
        
        yield
        
        print("🔒 Shutting down PostgreSQL connections...")
        await ownership_pool.close()


# Create FastAPI app with lifespan
app = FastAPI(
    title="CopilotKit Agent with History",
    description="Example FastAPI agent with persistent thread history",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add ownership endpoints (consumer-side implementation)
# This demonstrates how consumers layer ownership ON TOP of the library
ownership_router = create_ownership_router()
app.include_router(ownership_router)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "agent": "history_agent", "graph_ready": graph is not None}


def main():
    """Run the uvicorn server."""
    port = int(os.getenv("AGENT_PORT", "8123"))
    print(f"\n🚀 Starting agent server on http://localhost:{port}")
    print(f"📚 History endpoints (from library):")
    print(f"   GET  http://localhost:{port}/threads/{{thread_id}}/history")
    print(f"   GET  http://localhost:{port}/threads/{{thread_id}}/state")
    print(f"   GET  http://localhost:{port}/runs?thread_id={{thread_id}}")
    print(f"   POST http://localhost:{port}/runs/{{run_id}}/join")
    print(f"\n👤 Ownership endpoints (consumer implementation):")
    print(f"   GET  http://localhost:{port}/users/{{user_id}}/threads")
    print(f"   POST http://localhost:{port}/users/{{user_id}}/threads\n")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
    )


if __name__ == "__main__":
    main()
