<div align="center">

# 🩺 AI SRE Agent

### From incident signals to evidence-backed diagnosis.

A Gemini-powered Site Reliability Engineering prototype that investigates simulated microservice failures using **SigNoz logs and traces**—while making the AI investigation observable, too.

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Services-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-Instrumented-7B61FF?logo=opentelemetry)](https://opentelemetry.io/)
[![SigNoz](https://img.shields.io/badge/Observability-SigNoz-7B61FF)](https://signoz.io/)
[![Gemini](https://img.shields.io/badge/AI-Gemini-4285F4)](https://ai.google.dev/)
[![Hackathon](https://img.shields.io/badge/Agents%20of%20SigNoz-Top%20100%20%7C%20350%2B-7C3AED)](https://archive.wemakedevs.org/hackathons/signoz/projects/all)

[Project write-up](https://dev.to/polikeybhuvan/i-built-an-ai-sre-agent-that-doesnt-just-detect-incidents-it-investigates-them-2l01) · [Hackathon gallery](https://archive.wemakedevs.org/hackathons/signoz/projects/all) · [Report an issue](https://github.com/polikeybhuvan/signoz-ai-sre-agent/issues/new)

</div>

---

## Why this project?

An observability dashboard can show that a service is slow or returning errors. Figuring out **why** often takes an engineer through multiple steps: find a suspicious trace, inspect related logs, compare evidence across services, and decide what to investigate next.

**AI SRE Agent explores how an AI agent can handle that first pass.** It queries SigNoz for evidence, uses Gemini function calling to choose diagnostic tools, and produces a plain-English diagnosis with suggested next steps.

The application under investigation is a small microservices system with intentionally injected delays and failures. The diagnostic agent is instrumented with OpenTelemetry as well, so its own model calls, tool executions, timing, and usage metadata can be observed.

> **Hackathon recognition:** Selected among the **Top 100 projects out of 350+ submissions** at the international Agents of SigNoz Hackathon by WeMakeDevs. This is a learning and demonstration prototype—not a production incident-response platform.

## At a glance

| | |
|---|---|
| **Problem** | Debugging distributed failures requires correlating logs and traces across services. |
| **Approach** | A bounded, tool-calling Gemini agent gathers telemetry evidence from SigNoz. |
| **Observability** | OpenTelemetry captures both application activity and the agent's investigation. |
| **Guardrails** | Read-only diagnostic queries, a configurable step limit, and human-validated recommendations. |

## What it can do

- **Investigate dynamically** — Gemini selects which diagnostic tool to call based on the evidence it needs.
- **Inspect real telemetry** — Query SigNoz for slow traces, error logs, and traces containing errors.
- **Simulate failure scenarios** — Four FastAPI services introduce latency and failure behavior to generate useful troubleshooting signals.
- **Observe the agent itself** — Inspect investigation spans, tool calls, model timing, and token-usage attributes when supplied by the API.
- **Run a monitoring prototype** — Periodically check error-trace results and trigger an investigation when a threshold is reached.
- **Recommend next steps** — Produce an explainable starting hypothesis, not an automatic remediation.

## Architecture

\`\`\`mermaid
flowchart TD
    Traffic[Checkout traffic] --> Frontend[Frontend service :8001]
    Frontend --> Order[Order service :8002]
    Order --> Inventory[Inventory service :8003]
    Order --> SimAI[Simulated AI service :8004]

    Frontend -. logs and traces .-> SigNoz[SigNoz]
    Order -. logs and traces .-> SigNoz
    Inventory -. logs and traces .-> SigNoz
    SimAI -. logs and traces .-> SigNoz

    Agent[Gemini-powered diagnostic agent] -->|Read-only query API| SigNoz
    Agent -. agent spans and model metadata .-> SigNoz
    Agent --> Diagnosis[Diagnosis and suggested next steps]
\`\`\`

### The application services

| Service | Endpoint | Responsibility | Simulated behavior |
|---|---|---|---|
| \`frontend_service.py\` | \`localhost:8001/checkout\` | Entry point for checkout traffic | Downstream errors and failed requests |
| \`order_service.py\` | \`localhost:8002/order\` | Coordinates order processing | Random latency and transaction failures |
| \`inventory_service.py\` | \`localhost:8003/stock\` | Simulates an inventory lookup | Variable query delay and simulated outages |
| \`agent_service.py\` | \`localhost:8004/assist\` | Simulates an application's AI dependency | Slow responses and malformed response behavior |

**Important distinction:** \`agent_service.py\` is a simulated dependency in the application being monitored. The real Gemini-powered SRE investigator lives in \`agent_diagnose.py\`.

## How the AI investigation works

The Gemini-powered agent exposes three read-only tools:

| Tool | Evidence collected |
|---|---|
| \`get_slow_traces()\` | Slow root-level traces within a lookback window |
| \`get_error_logs()\` | Recent error-level logs, optionally filtered by service |
| \`get_error_traces()\` | Traces containing error spans |

The investigation follows a bounded tool-calling loop:

1. **Start with a question.** The agent receives an investigation goal and the tool definitions.
2. **Choose evidence.** Gemini requests a tool and provides its arguments.
3. **Query SigNoz.** Python runs the selected read-only query and returns the result.
4. **Reassess.** Gemini can request more evidence or move to a final response.
5. **Report.** The agent prints a plain-English diagnosis, a likely cause when supported, and a recommended next step.

The maximum number of agent steps is configurable through \`MAX_AGENT_STEPS\`. This bounds the investigation; it does not guarantee a correct diagnosis.

### Example: investigating a slow checkout

A possible investigation may begin with an unusually slow checkout trace, use error logs to narrow the likely service, and then inspect related error traces. The exact sequence depends on the telemetry returned and the model's tool choices.

The result is an **AI-generated hypothesis**. Engineers should verify it against the underlying traces and logs before acting.

## Observing the observer

The investigator is instrumented too. OpenTelemetry spans and attributes can make it possible to inspect the diagnostic run alongside application telemetry.

Depending on the path taken, a trace may contain spans for:

- The overall investigation and each agent step
- Gemini \`generate_content\` requests
- Diagnostic tool calls and returned result counts
- Agent decisions and total investigation steps
- Model name and token-usage metadata when returned by Gemini
- Execution timing and recorded errors

This makes the agent's own latency and tool behavior visible in SigNoz, rather than leaving the investigator as an opaque black box.

### Recorded investigation trace

![SigNoz trace waterfall from a recorded AI SRE investigation](trace-waterfall.png)

*This is a recorded trace from the project demonstration. The spans and timings of a new run will vary.*

## Demo results

The project’s documented demonstration reported the following values from a load test and an investigation captured in SigNoz.

| Measurement | Reported result |
|---|---:|
| Checkout requests | 195 |
| Successful requests | 158 |
| Failed requests | 37 |
| Success rate | 81.03% |
| Investigation steps | 3 |
| Tool calls | 2 |
| Investigation duration | Approximately 10.6 seconds |
| Spans in the recorded investigation trace | 14 |
| Errors in that recorded investigation trace | 0 |

The recorded trace showed that the final synthesis step accounted for approximately 40.78% of the investigation duration.

These are **historical demonstration results**, not performance guarantees or a controlled benchmark. Actual results depend on failure injection, telemetry availability, network latency, and Gemini response time.

## Technology stack

| Technology | Role |
|---|---|
| Python | Services and diagnostic logic |
| FastAPI | Microservice APIs |
| HTTPX | Inter-service HTTP calls and load generation |
| Google Gemini API | Function calling and diagnosis generation |
| SigNoz | Querying and exploring logs and distributed traces |
| OpenTelemetry | Instrumentation and trace export |
| Requests | HTTP requests to the SigNoz and Gemini APIs |
| python-dotenv | Local environment-variable configuration |

## Quick start

This guide runs the four application services as local Python processes. SigNoz runs separately and must be reachable from your machine.

### Prerequisites

- Python 3.10 or later
- Git
- A running SigNoz instance with its query API accessible
- An OTLP endpoint configured to accept telemetry
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/)

### 1. Clone and install

\`\`\`bash
git clone https://github.com/polikeybhuvan/signoz-ai-sre-agent.git
cd signoz-ai-sre-agent

python -m venv venv
\`\`\`

**Windows — Command Prompt**
\`\`\`bat
venv\\Scripts\\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
opentelemetry-bootstrap -a install
copy .env.example .env
\`\`\`

**macOS / Linux**
\`\`\`bash
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
opentelemetry-bootstrap -a install
cp .env.example .env
\`\`\`

### 2. Configure credentials

Edit your local \`.env\` file:

\`\`\`dotenv
SIGNOZ_URL=http://localhost:8080
SIGNOZ_API_KEY=YOUR_SIGNOZ_API_KEY
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=gemini-2.5-flash
MAX_AGENT_STEPS=5
LOOKBACK_MINUTES=15
\`\`\`

Replace the placeholders with valid credentials and adjust the SigNoz endpoint to your setup. Keep the real \`.env\` file local; do not commit credentials.

### 3. Start the four services

Open **a separate terminal for each service**. Activate the virtual environment in each terminal. The examples below use Windows Command Prompt and the default local OTLP endpoint; adjust it to match your SigNoz deployment.

**Frontend**
\`\`\`bat
set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
set OTEL_SERVICE_NAME=frontend-service
opentelemetry-instrument python frontend_service.py
\`\`\`

**Order**
\`\`\`bat
set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
set OTEL_SERVICE_NAME=order-service
opentelemetry-instrument python order_service.py
\`\`\`

**Inventory**
\`\`\`bat
set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
set OTEL_SERVICE_NAME=inventory-service
opentelemetry-instrument python inventory_service.py
\`\`\`

**Simulated AI dependency**
\`\`\`bat
set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
set OTEL_SERVICE_NAME=agent-service
opentelemetry-instrument python agent_service.py
\`\`\`

Keep all four processes running.

### 4. Generate traffic

In another activated terminal:

\`\`\`bash
python load_test.py
\`\`\`

The load generator sends repeated requests to \`http://localhost:8001/checkout\`, with randomized intervals. It runs continuously until you stop it with \`Ctrl+C\`. Give SigNoz time to receive telemetry before launching an investigation.

### 5. Run the AI SRE Agent

\`\`\`bat
set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
set OTEL_SERVICE_NAME=diagnosis-agent
opentelemetry-instrument python agent_diagnose.py
\`\`\`

The agent queries SigNoz, lets Gemini choose diagnostic tools, and prints its diagnosis.

The earlier fixed-query workflow is also available:

\`\`\`bash
python diagnose.py
\`\`\`

## Continuous monitoring prototype

\`monitor.py\` periodically checks error-trace results and invokes the agent when its threshold is reached. Current settings in the script are:

| Setting | Value |
|---|---:|
| Check interval | 60 seconds |
| Error-trace lookback | 5 minutes |
| Trigger threshold | 3 distinct trace IDs in returned results |
| Cooldown after a trigger | 180 seconds |

Run it with OpenTelemetry instrumentation:

\`\`\`bat
set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
set OTEL_SERVICE_NAME=diagnosis-agent
opentelemetry-instrument python monitor.py
\`\`\`

**Monitoring limitation:** the SigNoz query returns a limited set of rows. The script deduplicates trace IDs within those returned results, so traces outside the query result window may not be counted. This is a monitoring prototype, not a production alerting or remediation system.

## Repository map

\`\`\`text
signoz-ai-sre-agent/
├── frontend_service.py   # Checkout entry point
├── order_service.py      # Order workflow and failure injection
├── inventory_service.py  # Inventory lookup simulation
├── agent_service.py      # Simulated application AI dependency
├── agent_diagnose.py     # Gemini-powered, tool-calling SRE agent
├── diagnose.py           # Fixed-query diagnosis workflow
├── monitor.py            # Periodic error-trace monitoring prototype
├── json_logger.py        # Structured JSON logging
├── load_test.py          # Checkout traffic generator
├── requirements.txt      # Python dependencies
├── .env.example          # Safe configuration template
├── .gitignore            # Ignores local secrets and generated files
├── SECURITY.md           # Security policy
├── trace-waterfall.png   # Recorded SigNoz investigation trace
└── README.md
\`\`\`

## Security and limitations

This project is a prototype for learning, experimentation, and demonstration. It should not be deployed as a production incident-response system without additional engineering and security review.

- **Read-only diagnosis:** the agent collects evidence and suggests next steps; it does not automatically remediate services.
- **No dedicated metrics tool yet:** current investigation tools focus on logs and traces.
- **Capped query results:** the returned telemetry may not cover every relevant event or trace.
- **Simulated dependencies:** failure behavior is randomized and does not replace testing against a production-like database or external dependency.
- **LLM uncertainty:** generated diagnoses can be wrong or incomplete; verify evidence before taking action.
- **Environment-dependent setup:** SigNoz connectivity, credentials, OTLP configuration, and Gemini availability are required.
- **No automated test/CI workflow is currently configured in this repository.** Run the project carefully in a controlled environment and verify your telemetry setup manually.

### Credential hygiene

- Keep API keys in a local \`.env\` file or a suitably secured deployment environment.
- Never commit real keys or tokens.
- Rotate credentials immediately if they are exposed; removing a secret from the latest file does not remove it from Git history.
- Review [SECURITY.md](SECURITY.md) for vulnerability-reporting guidance.

## Roadmap

- [ ] Improve monitoring completeness, pagination, and recovery from partial query failures.
- [ ] Add metrics investigation and service-level objective context.
- [ ] Add automated tests and a CI workflow.
- [ ] Make failure scenarios more reproducible for repeatable evaluation.
- [ ] Generate structured incident reports with supporting evidence.
- [ ] Evaluate diagnosis quality against known failure scenarios.
- [ ] Package the services for reproducible local deployment.

## What I learned

This project reinforced a core lesson: **an AI agent needs evidence, useful tools, execution limits, and observability—not just a prompt.**

Building it brought together distributed-service behavior, telemetry queries, failure simulation, Gemini function calling, and instrumentation of the investigation itself. The idea is simple: make the investigation observable, not just the incident.

## Contributing

Bug reports and suggestions are welcome.

**[Report an issue](https://github.com/polikeybhuvan/signoz-ai-sre-agent/issues/new)** with reproduction steps and relevant logs. Remove API keys, tokens, and other sensitive information before sharing logs publicly. For larger changes, open an issue first to discuss the proposed approach.

---

<div align="center">

**Built for the Agents of SigNoz Hackathon · AI & Agent Observability**

[GitHub repository](https://github.com/polikeybhuvan/signoz-ai-sre-agent) · [Project write-up](https://dev.to/polikeybhuvan/i-built-an-ai-sre-agent-that-doesnt-just-detect-incidents-it-investigates-them-2l01) · [Official hackathon gallery](https://archive.wemakedevs.org/hackathons/signoz/projects/all)

</div>
