# EDGAR Agent

Full-stack AI agent that answers questions about public companies using SEC EDGAR 10-K filings fetched on demand. No LangChain or CrewAI — the agent loop is implemented manually.

## Stack

- **Backend**: FastAPI + SSE streaming, Python 3.11+
- **Frontend**: React 18 + Vite + TypeScript
- **Default model**: `claude-sonnet-5` (Anthropic)
- **Alt model**: NVIDIA NIM / Nemotron (OpenAI-compatible, config flag)
- **Data source**: SEC EDGAR full-text search API (no pre-ingestion)

## How the agent loop works

```
User message
    → POST /chat
        → load session history
        → model.create(tools=[search_edgar, fetch_filing])
        → while stop_reason == "tool_use":
              execute tools → append tool_result → re-prompt
        → stream final answer tokens via SSE
        → persist messages to session
```

## Setup

### 1. Clone & install Python deps

```
cd edgar-agent
pip install -r requirements.txt
```

### 2. Environment variables

Create a `.env` file in `edgar-agent/` (or export these):

```
ANTHROPIC_API_KEY=sk-ant-...
```

To use NVIDIA NIM instead of Anthropic:

```
MODEL_PROVIDER=nvidia
NVIDIA_API_KEY=nvapi-...
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=nvidia/llama-3.1-nemotron-ultra-253b-v1
```

### 3. Start the backend

```
cd edgar-agent/backend
uvicorn main:app --reload --port 8000
```

### 4. Start the frontend

```
cd edgar-agent/frontend
npm install
npm run dev
```

Open http://localhost:5173

## API

### `POST /chat`

```json
{ "message": "What was Apple's revenue in 2023?", "session_id": "optional-uuid" }
```

Streams SSE events:

| Event type | Payload |
|---|---|
| `token` | `{"type":"token","text":"..."}` |
| `tool_call` | `{"type":"tool_call","tool":"search_edgar","input":{...}}` |
| `session_id` | `{"type":"session_id","session_id":"uuid"}` |
| `done` | `{"type":"done","messages":[...]}` |

### `GET /sessions/{session_id}/history`

Returns full conversation history for a session.

## Tools

| Tool | Description |
|---|---|
| `search_edgar(company_name)` | Hits EDGAR full-text search API, returns list of 10-K filing URLs |
| `fetch_filing(url)` | Fetches + extracts text from a 10-K filing URL (first 12K chars) |

## Tests

Backend must be running on port 8000.

```
python tests/simulation_tests.py
```

5 scripted scenarios — checks that answers contain expected keywords.

```
python tests/eval.py
```

LLM-as-judge (uses `claude-sonnet-5`) — scores each of 5 conversations 1–5 on relevance and accuracy, prints averages.
