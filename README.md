# 🩺 AI SRE Agent

### From incident detection to evidence-based diagnosis.

**AI SRE Agent** is an AI-powered Site Reliability Engineering tool that investigates microservice failures using live observability data from SigNoz. Powered by Google's Gemini API and instrumented with OpenTelemetry, it dynamically investigates logs and distributed traces to identify likely root causes and recommend actionable next steps.

Instead of simply showing you another dashboard, it helps investigate the question: **What went wrong, and where should we look next?**

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python"></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-Microservices-009688?logo=fastapi" alt="FastAPI"></a>
  <a href="https://opentelemetry.io/"><img src="https://img.shields.io/badge/Telemetry-OpenTelemetry-7B61FF?logo=opentelemetry" alt="OpenTelemetry"></a>
  <a href="https://signoz.io/"><img src="https://img.shields.io/badge/Observability-SigNoz-7B61FF" alt="SigNoz"></a>
  <a href="https://ai.google.dev/"><img src="https://img.shields.io/badge/LLM-Gemini-4285F4" alt="Gemini"></a>
</p>

<p align="center">
  **Built for the Agents of SigNoz Hackathon · AI & Agent Observability**
</p>

<p align="center">
  <a href="https://dev.to/polikeybhuvan/i-built-an-ai-sre-agent-that-doesnt-just-detect-incidents-it-investigates-them-2l01">Project Write-up</a> ·
  <a href="https://github.com/polikeybhuvan/signoz-ai-sre-agent/issues">Report an Issue</a>
</p>

---

## 📌 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Architecture](#-architecture)
- [How the Agent Works](#-how-the-agent-works)
- [Observing the Observer](#-observing-the-observer)
- [Demo Results](#-demo-results)
- [Technology Stack](#-technology-stack)
- [Getting Started](#-getting-started)
- [Project Structure](#-project-structure)
- [Limitations](#-limitations)
- [Roadmap](#-roadmap)

## 🔍 Overview

Observability platforms help engineers detect errors, latency spikes, and service degradation. Diagnosing the underlying cause, however, often requires manually inspecting traces, correlating logs, forming hypotheses, and deciding what to investigate next.

AI SRE Agent automates the initial investigation.

The system combines a deliberately failure-prone microservices application with an AI agent that queries SigNoz for evidence. Using Gemini function calling, the agent chooses which investigation tool to use, examines the results, and determines whether further investigation is needed.

The agent is also instrumented with OpenTelemetry. Its own LLM requests, investigation steps, tool executions, and token usage can be inspected in SigNoz.

**The core idea: make the investigation observable, not just the incident.**

## ✨ Features

- **Dynamic AI investigation:** Gemini chooses among available diagnostic tools based on the investigation context.
- **Live telemetry queries:** Retrieves slow traces, error logs, and traces containing errors from SigNoz.
- **Microservice failure simulation:** Four FastAPI services introduce variable latency, transaction failures, downstream errors, and malformed AI responses.
- **AI observability:** Uses OpenTelemetry spans to track the diagnostic agent's execution.
- **LLM usage tracking:** Records token usage returned by Gemini and attributes it to the relevant request.
- **Continuous monitoring prototype:** Checks for error traces and triggers an AI investigation when a configured threshold is met.
- **Human-readable diagnosis:** Produces an explanation of likely problems and recommends a next step.
- **Read-only investigation tools:** The agent collects evidence and offers recommendations; it does not automatically remediate incidents.

## 🏗️ Architecture

```text
                    Checkout Traffic
                           |
                           v
                +----------------------+
                |  Frontend Service    |
                |      Port 8001       |
                +----------+-----------+
                           |
                           v
                +----------------------+
                |   Order Service      |
                |      Port 8002       |
                +----------+-----------+
                           |
                    +------+------+
                    |             |
                    v             v
           +----------------+ +----------------+
           | Inventory      | | Simulated AI   |
           | Service :8003  | | Service :8004  |
           +----------------+ +----------------+
                    |
          Application Telemetry
                    |
                    v
             +-------------+
             |   SigNoz    |
             |  Logs and   |
             |   Traces    |
             +------+------+
                    ^
                    |
           Telemetry Queries
                    |
             +------+------+
             | AI SRE Agent|
             | Gemini +    |
             | 3 Tools     |
             +------+------+
                    |
                    v
          Diagnosis and Next Steps
```

The application services generate telemetry that is sent to SigNoz through OpenTelemetry. The diagnostic agent queries SigNoz, sends the collected evidence to Gemini as needed, and produces its diagnosis.

The simulated AI service and the diagnostic agent serve different purposes: one introduces failures into the application workflow, while the other investigates those failures.

### Microservices

| Service | Port | Responsibility | Simulated failure scenarios |
|---|---:|---|---|
| `frontend-service` | 8001 | Accepts checkout requests and calls the order service. | Downstream failures and HTTP errors |
| `order-service` | 8002 | Coordinates inventory checks and the simulated AI call. | Random delays, transaction failures, downstream errors |
| `inventory-service` | 8003 | Simulates an inventory database lookup. | Query latency and connection-pool exhaustion |
| `agent-service` | 8004 | Simulates an application's AI dependency. | Slow responses and malformed response structures |

These services deliberately introduce instability so the diagnostic agent has meaningful telemetry to investigate.

## 🧠 How the Agent Works

The diagnostic agent is implemented in `agent_diagnose.py`. It uses Gemini function calling to select from three read-only tools.

| Tool | Purpose |
|---|---|
| `get_slow_traces()` | Retrieves the slowest root-level traces in a specified lookback window. |
| `get_error_logs()` | Retrieves recent error-level logs, optionally filtered by service. |
| `get_error_traces()` | Retrieves traces containing error spans. |

### Investigation workflow

**1. Investigate**

The agent receives an investigation objective and the available tool definitions.

**2. Select a tool**

Gemini decides which tool to call and supplies the arguments.

**3. Gather evidence**

Python executes the selected tool against the SigNoz query API and returns its results to Gemini.

**4. Evaluate the results**

Gemini interprets the returned evidence and decides whether another tool call is required.

**5. Produce a diagnosis**

When it has enough evidence, the model produces a plain-English diagnosis and recommends a concrete next investigation step. The loop is bounded by a configurable maximum number of steps.

### Example investigation

Consider a checkout request that takes several seconds to complete.

1. **Find the symptom:** Slow traces reveal unusually long checkout requests.
2. **Narrow the investigation:** Error logs indicate that the frontend is waiting on an unsuccessful order-service request.
3. **Recommend the next step:** The agent identifies the order service or a downstream dependency as a likely cause and recommends examining the relevant error traces.

This is an illustrative investigation, not a guaranteed sequence. The actual tool calls depend on the telemetry returned and the model's decisions.

The agent can identify likely causes, but its output is a hypothesis that should be validated by an engineer.

## 🔭 Observing the Observer

A distinguishing feature of this project is that the diagnostic agent itself is observable.

OpenTelemetry spans represent the overall investigation, its individual steps, Gemini requests, and tool executions.

```text
agent.investigation
├── agent.step.1
│   └── gemini.generate_content
├── agent.tool_call.get_slow_traces
├── agent.step.2
│   └── gemini.generate_content
├── agent.tool_call.get_error_logs
└── agent.step.3
    └── gemini.generate_content
```

The displayed tree is illustrative; the actual span structure depends on the investigation path and number of tool calls.

The implementation records attributes including:

- LLM provider and requested model
- Prompt, completion, and total token usage when returned by the API
- Investigation step and agent decision
- Tool names, arguments, and result counts
- Execution timing for LLM requests and tools

This makes it possible to investigate not only application failures but also the diagnostic agent's latency, execution path, and token consumption.

## 📊 Demo Results

The project README previously documented an end-to-end demonstration captured in SigNoz with the following results.

| Measurement | Reported result |
|---|---:|
| Checkout requests | 195 |
| Successful requests | 158 |
| Failed requests | 37 |
| Success rate | 81.03% |
| Investigation steps | 3 |
| Tool calls | 2 |
| Investigation duration | Approximately 10.6 seconds |
| Investigation trace spans | 14 |
| Errors in the recorded investigation trace | 0 |

The documented trace showed that the final synthesis step accounted for approximately 40.78% of the total investigation duration.

These numbers describe the recorded demonstration, not guaranteed performance benchmarks. Results vary with the simulated failures, available telemetry, network latency, and LLM response times.

### Investigation Trace

![SigNoz trace waterfall for an AI SRE investigation](trace-waterfall.png)

*SigNoz trace waterfall showing the diagnostic agent's execution and timing breakdown.*

## 🧰 Technology Stack

| Technology | Role |
|---|---|
| Python | Application and agent implementation |
| FastAPI | Microservice APIs |
| HTTPX | HTTP communication between services and the load generator |
| Gemini API | LLM reasoning and function calling |
| SigNoz | Observability queries and telemetry visualization |
| OpenTelemetry | Distributed tracing and agent instrumentation |
| Requests | HTTP calls to SigNoz and Gemini |
| python-dotenv | Loading local environment configuration |

## 🚀 Getting Started

### Prerequisites

Before running the project, prepare:

- Python 3.10 or later
- A running SigNoz instance with its query API accessible
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/)
- Access to the configured SigNoz OTLP endpoint
- Git and a terminal

The steps below run the four application services as local Python processes. SigNoz can be deployed separately, including through Docker.

### 1. Clone the repository

```bash
git clone https://github.com/polikeybhuvan/signoz-ai-sre-agent.git
cd signoz-ai-sre-agent
```

### 2. Create a virtual environment

**Windows — Command Prompt**

```bat
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
opentelemetry-bootstrap -a install
```

The repository's `requirements.txt` includes the application dependencies, `requests`, `python-dotenv`, and OpenTelemetry packages.

### 4. Configure environment variables

Create a local file named `.env` in the repository root, using `.env.example` as a template.

```dotenv
SIGNOZ_URL=http://localhost:8080
SIGNOZ_API_KEY=YOUR_SIGNOZ_API_KEY
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=gemini-2.5-flash
MAX_AGENT_STEPS=5
LOOKBACK_MINUTES=15
```

Replace the placeholder values with valid credentials. Adjust the SigNoz URL and model settings to match your environment and account access.

**Security essentials**

- Never commit `.env` or real credentials to GitHub.
- Keep `.env.example` free of secrets.
- Rotate credentials that have been exposed.
- Keep `.env` excluded in `.gitignore`.
- If a secret was committed previously, remove it from Git history as well as rotating it. Removing it from the latest file alone is insufficient.

### 5. Start SigNoz and the microservices

Ensure that SigNoz is running and that its query API and OTLP endpoint are accessible.

Open a separate terminal for each service. Activate the virtual environment in each terminal, set the OTLP endpoint and service name, and start the service.

The following commands use Windows Command Prompt. The OTLP endpoint may differ depending on your SigNoz deployment.

**Frontend service**

```bat
set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
set OTEL_SERVICE_NAME=frontend-service
opentelemetry-instrument python frontend_service.py
```

**Order service**

```bat
set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
set OTEL_SERVICE_NAME=order-service
opentelemetry-instrument python order_service.py
```

**Inventory service**

```bat
set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
set OTEL_SERVICE_NAME=inventory-service
opentelemetry-instrument python inventory_service.py
```

**Simulated AI service**

```bat
set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
set OTEL_SERVICE_NAME=agent-service
opentelemetry-instrument python agent_service.py
```

Keep each service running in its own terminal. Confirm the ports and endpoint configuration match your local setup.

### 6. Generate checkout traffic

Open another terminal and run:

```bash
python load_test.py
```

The load generator repeatedly sends checkout requests and reports successful and failed requests. The simulated services introduce latency and occasional failures, producing telemetry for SigNoz to collect.

Allow some traffic to accumulate before starting an investigation.

### 7. Run the AI SRE agent

Open another terminal and activate the virtual environment.

```bat
set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
set OTEL_SERVICE_NAME=diagnosis-agent
opentelemetry-instrument python agent_diagnose.py
```

The agent queries SigNoz, uses Gemini function calling to choose investigation tools, and prints the resulting diagnosis.

The earlier fixed-query diagnostic workflow can be run separately:

```bash
python diagnose.py
```

### 8. Run the monitoring prototype

The project also includes `monitor.py`, a continuous monitoring loop that periodically checks error traces.

```bat
set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
set OTEL_SERVICE_NAME=diagnosis-agent
opentelemetry-instrument python monitor.py
```

The current prototype checks every 60 seconds, searches a five-minute lookback window, triggers an investigation when at least three returned error-trace rows are observed, and applies a three-minute cooldown after a trigger.

This implementation counts returned rows rather than explicitly deduplicated trace IDs. It should be treated as a prototype rather than production-ready alert management.

## 📁 Project Structure

```text
signoz-ai-sre-agent/
├── frontend_service.py   # Checkout entry point
├── order_service.py      # Order orchestration and injected failures
├── inventory_service.py  # Inventory and database-failure simulation
├── agent_service.py      # Simulated AI dependency
├── agent_diagnose.py     # Gemini-powered diagnostic agent
├── diagnose.py           # Fixed-query diagnostic workflow
├── monitor.py            # Continuous monitoring prototype
├── json_logger.py        # Structured JSON logging
├── load_test.py          # Checkout traffic generator
├── requirements.txt      # Python dependencies
├── .env.example          # Safe configuration template
├── .gitignore            # Excludes local secrets and generated files
├── SECURITY.md           # Security policy
├── trace-waterfall.png   # Recorded SigNoz investigation trace
└── README.md
```

The real `.env` file belongs only in your local environment and should never be committed to the repository.

## ⚠️ Limitations

This is a prototype for learning, experimentation, and demonstration.

- The diagnostic tools query logs and traces; a dedicated metrics-investigation tool has not yet been implemented.
- The application services simulate failures rather than connecting to a production database or real external AI dependency.
- LLM diagnoses may be incomplete or incorrect and require engineer validation.
- The monitoring loop uses a basic threshold and cooldown.
- The agent recommends next steps but does not perform automatic remediation.
- Successful operation depends on accessible SigNoz telemetry, valid credentials, and Gemini API availability.

## 🗺️ Roadmap

- [ ] Improve monitoring reliability, exception recovery, and distinct-trace counting.
- [ ] Add richer, reproducible failure scenarios.
- [ ] Generate structured incident reports with supporting evidence.
- [ ] Add metrics analysis and service-level objective context.
- [ ] Explore integrating the SigNoz MCP server instead of handwritten query tools.
- [ ] Evaluate multi-agent investigation across logs, traces, and metrics.
- [ ] Add automated tests and continuous integration.
- [ ] Package the services for reproducible deployment.
- [ ] Evaluate diagnosis quality against known failure scenarios.

## 💡 What I Learned

Building this project reinforced that an effective AI agent requires more than an LLM and a prompt. It needs useful tools, reliable telemetry, realistic failure scenarios, bounded execution, and observability into its own behavior.

Working through service networking, SigNoz setup, OpenTelemetry configuration, and telemetry queries also showed how much real-world SRE work involves infrastructure and evidence gathering—not simply interpreting error messages.

The central idea behind this project is simple:

**Make the investigation observable, not just the incident.**

## 🤝 Contributing

Bug reports, suggestions, and contributions are welcome.

For substantial changes, open an issue first to discuss the proposed work.

---

<p align="center">

**Built solo for the Agents of SigNoz Hackathon · AI & Agent Observability**

If you find this project interesting, consider starring the repository.

[View on GitHub](https://github.com/polikeybhuvan/signoz-ai-sre-agent)

</p>
