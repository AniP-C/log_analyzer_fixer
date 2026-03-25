# FlowFix Agent

FlowFix Agent is a lightweight FastAPI app that simulates an AI-powered SRE assistant for order-processing incidents. It detects the issue type, retrieves similar incidents, reasons about the best action, simulates execution, and sends a simulated notification.

## Features

- `POST /analyze` for end-to-end incident remediation
- `POST /benchmark` to score the agent across bundled test cases
- `GET /health` for a simple health check
- Minimal debug UI at `/`
- Optional OpenAI-backed reasoning via environment variables, with a deterministic fallback so the app runs immediately

## Project Structure

```text
flowfix-agent/
├── app/
├── evaluation/
├── README.md
├── requirements.txt
└── .cursorrules
```

## Quick Start

```bash
python -m uv venv .venv
python -m uv sync
python -m uv run uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000` for the debug UI.

## Environment Variables

Create a `.env` file if you want live LLM reasoning:

```env
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4.1-mini
APP_ENV=development
RESPONSE_TIME_TARGET_MS=1500
```

Without `OPENAI_API_KEY`, FlowFix uses deterministic fallback classification and reasoning.

## Alternative Install

If you want plain pip instead of `uv`, `requirements.txt` is still included.

## Example Request

```bash
curl -X POST "http://127.0.0.1:8000/analyze" ^
  -H "Content-Type: application/json" ^
  -d "{\"input\":\"Order 123 stuck in processing\"}"
```

## Benchmarking

```bash
python -m uv run python -m evaluation.benchmark
```

Benchmark results are saved to `evaluation/results.json`.
