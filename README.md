# FastAPI + Next.js Example

This example demonstrates CopilotKit with a self-hosted FastAPI LangGraph agent and persistent thread history.

## Features

- ✅ **FastAPI Agent Server** - Self-hosted LangGraph agent with `LangGraphAGUIAgent`
- ✅ **PostgreSQL Persistence** - Thread history survives server restarts
- ✅ **History Hydration** - Messages restored on page refresh
- ✅ **Thread Switching** - Switch between conversations seamlessly
- ✅ **Custom History Client** - TypeScript client for FastAPI endpoints

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Next.js Frontend (port 3001)                │
│  - CopilotKit React components                                  │
│  - Custom HistoryClientInterface                                │
│  - HistoryHydratingAgentRunner                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FastAPI Backend (port 8123)                    │
│  - LangGraphAGUIAgent for AG-UI protocol                        │
│  - add_history_endpoints() for history API                      │
│  - PostgreSQL checkpointer for persistence                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PostgreSQL Database                           │
│  - Checkpoint storage                                           │
│  - Thread history                                               │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

- **Node.js 18+** - For the Next.js frontend
- **Python 3.9+** - For the FastAPI agent
- **PostgreSQL** - For checkpoint persistence
- **OpenAI API Key** - For the LLM

## Quick Start

### 1. Set Up PostgreSQL

Make sure you have a PostgreSQL database running. You can use Docker:

```bash
docker run -d \
  --name copilotkit-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=copilotkit_history \
  -p 5432:5432 \
  postgres:16
```

### 2. Configure Environment

Copy the example environment file:

```bash
cp env.example .env
```

Edit `.env` with your values:

```env
OPENAI_API_KEY=sk-your-openai-api-key
DATABASE_URL=postgresql://postgres:password@localhost:5432/copilotkit_history
AGENT_PORT=8123
NEXT_PUBLIC_AGENT_URL=http://localhost:8123
```

### 3. Start the FastAPI Agent

```bash
cd agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Initialize the database (creates checkpoint tables)
python -c "
from langgraph.checkpoint.postgres import PostgresSaver
import os
from dotenv import load_dotenv
load_dotenv('../.env')
saver = PostgresSaver.from_conn_string(os.getenv('DATABASE_URL'))
saver.setup()
print('Database initialized!')
"

# Start the server
python main.py
```

The agent will be available at `http://localhost:8123`.

### 4. Start the Next.js UI

In a new terminal:

```bash
cd ui

# Install dependencies
npm install

# Copy environment
cp ../.env .env.local

# Start the development server
npm run dev
```

The UI will be available at `http://localhost:3001`.

## Testing History Persistence

1. **Open the UI** at `http://localhost:3001`

2. **Send some messages** to the agent:
   - "What's the weather in New York?"
   - "What time is it?"
   - "Tell me a joke"

3. **Refresh the page** - Your messages should still be there!

4. **Create a new thread** using the sidebar

5. **Switch between threads** - Each thread has its own history

6. **Restart the server** - History is still preserved (thanks to PostgreSQL)

## API Endpoints

The FastAPI server exposes these endpoints:

### AG-UI Protocol (for CopilotKit)
- `POST /` - Main agent endpoint

### History API (for copilotkit-langgraph-history)
- `GET /threads/{thread_id}/history` - Fetch checkpoint history
- `GET /threads/{thread_id}/state` - Get current thread state
- `GET /runs?thread_id={thread_id}` - List runs for a thread
- `POST /runs/{run_id}/join` - Join an active run stream

### Health Check
- `GET /health` - Server health status

## How It Works

### 1. Custom History Client

The UI creates a custom `HistoryClientInterface` that talks to FastAPI:

```typescript
// ui/src/lib/custom-history-client.ts
const customHistoryClient = createFastAPIHistoryClient(AGENT_URL);
```

### 2. History Hydrating Runner

The CopilotKit API route uses the custom client:

```typescript
// ui/src/app/api/copilotkit/route.ts
const runner = new HistoryHydratingAgentRunner({
  agent,
  client: customHistoryClient,  // Custom client for FastAPI
  historyLimit: 100,
});
```

### 3. FastAPI History Endpoints

The agent adds history endpoints with one line:

```python
# agent/main.py
from copilotkit_history import add_history_endpoints

add_history_endpoints(app, graph)
```

## Customization

### Adding New Tools

Edit `agent/agent.py` to add new tools:

```python
@tool
def my_new_tool(param: str) -> str:
    """Description for the LLM."""
    return f"Result: {param}"

tools = [get_weather, get_time, my_new_tool]
```

### Changing the Model

In `agent/agent.py`:

```python
model = ChatOpenAI(model="gpt-4o", temperature=0.7)
```

### Adding State Fields

Extend `AgentState` in `agent/agent.py`:

```python
class AgentState(CopilotKitState):
    my_custom_field: str = ""
```

## Troubleshooting

### "Connection refused" errors

- Make sure the FastAPI agent is running on port 8123
- Check that `NEXT_PUBLIC_AGENT_URL` in `.env.local` is correct

### "No history found"

- Verify PostgreSQL is running and accessible
- Check `DATABASE_URL` is correct
- Run the database initialization script

### Messages not persisting

- Ensure you're using PostgresSaver, not MemorySaver
- Check the database has the checkpoint tables

## License

MIT


