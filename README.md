\# AI SRE Agent on SigNoz



An AI agent that investigates real microservice failures by autonomously querying live

observability data from a self-hosted \*\*SigNoz\*\* instance — traces, logs, and metrics —

and produces a plain-English root-cause diagnosis. Built for the \*\*Agents of SigNoz\*\*

hackathon (AI \& Agent Observability track).



Unlike a fixed monitoring script, this agent decides for itself which SigNoz query to

run next based on what it's already found — starting broad, then narrowing in on the

service that looks most suspicious. Its own reasoning process (each step, each tool

call, each LLM call) is itself instrumented with OpenTelemetry, so it shows up as a

trace in SigNoz alongside the system it's diagnosing.



\*\*Blog post:\*\* \[link here once published]

\*\*Demo video:\*\* \[link here once recorded]



\## Architecture



```

frontend-service (8001) → order-service (8002) → inventory-service (8003)

&#x20;                               ↓

&#x20;                        agent-service (8004)  \[simulated LLM/AI call]

```



Four small FastAPI services chained together, deliberately instrumented with realistic

failure modes:



\- \*\*frontend-service\*\* — entry point (`/checkout`)

\- \*\*order-service\*\* — calls inventory + a simulated AI agent step; injects random

&#x20; delay, occasional 500/502 errors, and simulated deadlock errors

\- \*\*inventory-service\*\* — simulates a slow DB call; occasionally exhausts its

&#x20; connection pool (503)

\- \*\*agent-service\*\* — simulates an LLM call with fake token counts and occasional

&#x20; malformed/"hallucinated" responses that order-service has to catch and fall back on



All four are auto-instrumented with OpenTelemetry and export traces, logs, and metrics

to SigNoz over OTLP.



On top of this sits the \*\*diagnosis agent\*\* (`agent\_diagnose.py`) — a Python script

using Gemini's function-calling API with three tools:



\- `get\_error\_logs` — fetch recent ERROR-level structured logs, optionally filtered

&#x20; to one service

\- `get\_slow\_traces` — fetch the slowest root-level traces across all services

\- `get\_error\_traces` — fetch traces containing at least one error span



The agent loops (up to 5 steps): call a tool → inspect the result → decide whether to

investigate further or give a final diagnosis. Every step and tool call is wrapped in

an OpenTelemetry span, so the investigation itself is visible in SigNoz as

`diagnosis-agent`.



\## Running it



\*\*Prerequisites:\*\* Docker, Python 3.10+, a self-hosted SigNoz instance

(\[install guide](https://signoz.io/docs/install/self-host/)), and a Gemini API key

from \[Google AI Studio](https://aistudio.google.com/).



```bash

python -m venv venv

venv\\Scripts\\activate        # or `source venv/bin/activate` on Mac/Linux

pip install -r requirements.txt

pip install opentelemetry-distro opentelemetry-exporter-otlp

opentelemetry-bootstrap -a install

```



Run each service in its own terminal, with OpenTelemetry instrumentation pointed at

your SigNoz OTLP endpoint:



```bash

set OTEL\_EXPORTER\_OTLP\_ENDPOINT=http://localhost:4317

set OTEL\_SERVICE\_NAME=frontend-service

opentelemetry-instrument python frontend\_service.py

```



(repeat for `order\_service.py`, `inventory\_service.py`, `agent\_service.py` with their

matching service names)



Generate traffic:



```bash

python load\_test.py

```



Fill in `SIGNOZ\_API\_KEY` and `GEMINI\_API\_KEY` in `agent\_diagnose.py`, then run the

agent:



```bash

set OTEL\_SERVICE\_NAME=diagnosis-agent

opentelemetry-instrument python agent\_diagnose.py

```



\## Files



| File | Purpose |

|---|---|

| `frontend\_service.py`, `order\_service.py`, `inventory\_service.py`, `agent\_service.py` | The flaky microservices chain |

| `json\_logger.py` | Shared structured JSON logging helper |

| `load\_test.py` | Continuous traffic generator |

| `agent\_diagnose.py` | The tool-calling AI diagnosis agent |

| `diagnose.py` | Earlier, simpler fixed-query version (kept for reference) |

| `monitor.py` | Continuous monitoring loop that triggers the agent when error rates spike |



\## What's next



\- Instrument more realistic failure scenarios

\- Turn the monitoring loop into a lightweight always-on service

\- Explore SigNoz's MCP server as an alternative to direct API calls for the agent's tools

