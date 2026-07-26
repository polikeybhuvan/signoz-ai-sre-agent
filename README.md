# 🩺 AI SRE Agent on SigNoz

**An AI agent that investigates production incidents — not just detects them.**

Built for the **Agents of SigNoz** hackathon (AI & Agent Observability track), this agent autonomously queries live traces, logs, and metrics from a self-hosted SigNoz instance, decides what to look at next, and produces a plain-English root-cause diagnosis — the way an SRE actually works an incident.

📝 **Blog post:** [I Built an AI SRE Agent That Doesn't Just Detect Incidents — It Investigates Them](https://dev.to/polikeybhuvan/i-built-an-ai-sre-agent-that-doesnt-just-detect-incidents-it-investigates-them-2l01)
🎥 **Demo video:** *[link here once recorded]*

---

## Why this exists

Most observability platforms are excellent at telling you *what* broke — which service is slow, which requests are failing, which logs contain errors. But turning that into *why* it broke still takes an engineer manually opening traces, searching logs, comparing services, and forming a hypothesis.

This project asks a simple question: **can an AI run that investigation itself?**

Not by stuffing thousands of logs into one giant prompt. Not by following a hardcoded script. But by reasoning step by step — deciding what to inspect first, what that result implies, and what to check next — until it has enough evidence to name a root cause.

## How it works

Four small FastAPI services are chained together to simulate a realistic (and realistically flaky) checkout flow:

```
frontend-service (8001) → order-service (8002) → inventory-service (8003)
                                ↓
                         agent-service (8004)   [simulated LLM/AI call]
```

| Service | Role |
|---|---|
| **frontend-service** | Entry point (`/checkout`) |
| **order-service** | Calls inventory + a simulated AI agent step; injects random delay, occasional 500/502 errors, and simulated deadlocks |
| **inventory-service** | Simulates a slow DB call; occasionally exhausts its connection pool (503) |
| **agent-service** | Simulates an LLM call with fake token counts and occasional malformed/"hallucinated" responses that `order-service` has to catch and fall back on |

All four are auto-instrumented with OpenTelemetry and export traces, logs, and metrics to SigNoz over OTLP — giving realistic, production-shaped telemetry (latency spikes, partial failures, connection exhaustion) for the agent to actually reason about.

### The diagnosis agent

On top of this sits `agent_diagnose.py` — a Python script using **Gemini's function-calling API** with three tools:

- `get_slow_traces` — fetch the slowest root-level traces across all services
- `get_error_logs` — fetch recent ERROR-level structured logs, optionally filtered to one service
- `get_error_traces` — fetch traces containing at least one error span

The agent loops for up to 5 steps: call a tool → inspect the result → decide whether to dig deeper or deliver a final diagnosis. Nothing about the investigation path is hardcoded; the model chooses the tools, the order, and when it has enough evidence.

**A real run looked like this:**

1. **Cast a wide net** — `get_slow_traces()` turns up several ~6s requests, all pointing at `frontend-service` on `GET /checkout`.
2. **Narrow in** — `get_error_logs(frontend-service)` reveals the frontend was actually waiting on `order-service`, which was returning HTTP 502.
3. **Diagnose** — the agent concludes the root cause likely sits in `order-service` or a downstream dependency, and recommends the next investigation step instead of overstating its confidence.

### Observing the observer

Every step of the agent's own reasoning — each LLM call, each tool call — is wrapped in an OpenTelemetry span, so the investigation itself shows up in SigNoz as a `diagnosis-agent` trace:

```
agent.investigation
├── agent.step.1
│      ├── Gemini API call
│      └── get_slow_traces()
├── agent.step.2
│      ├── Gemini API call
│      └── get_error_logs()
└── agent.step.3
       └── Final diagnosis
```

Each span records prompt/completion/total tokens, response latency, and tool execution timing — so the same platform used to debug the application is also used to debug the AI making decisions about it.

---

## Getting started

### Prerequisites

- Docker
- Python 3.10+
- A self-hosted SigNoz instance ([install guide](https://signoz.io/docs/install/self-host/))
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/)

### 1. Install dependencies

```bash
python -m venv venv
venv\Scripts\activate        # or `source venv/bin/activate` on Mac/Linux
pip install -r requirements.txt
pip install opentelemetry-distro opentelemetry-exporter-otlp
opentelemetry-bootstrap -a install
```

### 2. Start the microservices

Run each service in its own terminal, pointed at your SigNoz OTLP endpoint:

```bash
set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
set OTEL_SERVICE_NAME=frontend-service
opentelemetry-instrument python frontend_service.py
```

Repeat for `order_service.py`, `inventory_service.py`, and `agent_service.py`, swapping in the matching `OTEL_SERVICE_NAME` each time.

### 3. Generate traffic

```bash
python load_test.py
```

This continuously fires checkout requests — some succeed, some fail, some run slow — so there's real, noisy telemetry in SigNoz for the agent to investigate.

### 4. Run the agent

Fill in `SIGNOZ_API_KEY` and `GEMINI_API_KEY` in `agent_diagnose.py`, then:

```bash
set OTEL_SERVICE_NAME=diagnosis-agent
opentelemetry-instrument python agent_diagnose.py
```

---

## Project structure

| File | Purpose |
|---|---|
| `frontend_service.py`, `order_service.py`, `inventory_service.py`, `agent_service.py` | The flaky microservices chain |
| `json_logger.py` | Shared structured JSON logging helper |
| `load_test.py` | Continuous traffic generator |
| `agent_diagnose.py` | The tool-calling AI diagnosis agent |
| `diagnose.py` | Earlier, simpler fixed-query version (kept for reference) |
| `monitor.py` | Continuous monitoring loop that triggers the agent when error rates spike |

---

## What I learned

Dashboards answer questions you already know to ask. Investigations begin when you don't know what question to ask next — and that's exactly where an AI agent earns its keep: not by replacing an SRE, but by automating the repetitive first pass of an incident investigation.

Most of the build time, ironically, went into infrastructure rather than agent logic — WSL and Docker networking, ClickHouse startup issues, and getting OpenTelemetry configured correctly. That's a fairly honest reflection of what building real observability tooling looks like.

## What's next

- Turn the monitoring loop into a lightweight, always-on service that triggers investigations automatically when error rates spike
- More realistic production failure scenarios
- Auto-generated incident reports after every investigation
- Swap the handwritten API tools for SigNoz's **MCP server**
- Multi-agent collaboration — specialized agents for logs, metrics, and traces that investigate independently before combining findings

---

If you have suggestions, ideas, or feedback, open an issue or reach out — always happy to hear them.
