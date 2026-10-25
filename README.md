 <div align="center">

# 🩺 AI SRE Agent

### From incident detection to evidence-based diagnosis.

An AI-powered Site Reliability Engineering agent that investigates microservice failures using live observability data from SigNoz. It analyzes logs and distributed traces, dynamically chooses what to investigate next, and produces a human-readable diagnosis with actionable next steps.

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Microservices-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![OpenTelemetry](https://img.shields.io/badge/Observability-OpenTelemetry-7B61FF?logo=opentelemetry)](https://opentelemetry.io/)
[![SigNoz](https://img.shields.io/badge/Telemetry-SigNoz-7B61FF)](https://signoz.io/)
[![Gemini](https://img.shields.io/badge/LLM-Gemini-4285F4)](https://ai.google.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](#license)

**Built for the Agents of SigNoz Hackathon · AI & Agent Observability**

[Project write-up](https://dev.to/polikeybhuvan/i-built-an-ai-sre-agent-that-doesnt-just-detect-incidents-it-investigates-them-2l01) · [Report an issue](https://github.com/polikeybhuvan/signoz-ai-sre-agent/issues)

</div>

---

## Overview

Modern observability platforms help engineers discover errors, latency spikes, and service degradation. However, diagnosing the underlying problem often requires an engineer to manually inspect traces, correlate logs, form hypotheses, and decide what evidence to gather next.

**AI SRE Agent automates this initial investigation.**

It connects an LLM to live SigNoz telemetry through three read-only investigation tools. Rather than executing a single fixed diagnostic script, the agent can select a tool, inspect its results, and decide whether additional evidence is needed before producing a diagnosis.

The agent's own execution is instrumented with OpenTelemetry, allowing its investigation steps, LLM calls, tool calls, latency, and token usage to be inspected in SigNoz as well.

The goal is not to replace an SRE engineer. It is to reduce repetitive initial investigation and help engineers get from an alert to a useful starting hypothesis faster.

## Key features

- **Agentic investigation:** The LLM selects investigation tools dynamically rather than following a completely fixed query sequence.
- **Live observability data:** Queries SigNoz for slow traces, error logs, and traces containing errors.
- **Distributed microservice simulation:** Four FastAPI services introduce realistic delays, failures, and downstream dependencies.
- **Observable AI execution:** OpenTelemetry spans expose the diagnostic agent's execution path.
- **Token and latency tracking:** Captures Gemini token usage and measures individual investigation steps and tool executions.
- **Continuous monitoring prototype:** A monitoring loop checks error traces and triggers an investigation when a configured threshold is reached.
- **Read-only diagnosis:** The agent gathers evidence and recommends next steps; it does not automatically modify production systems or execute remediation.

## Architecture

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
                +-----+-----------+----+
                      |           |
                      v           v
           +----------------+  +----------------+
           | Inventory      |  | Simulated AI   |
           | Service :8003  |  | Service :8004  |
           +----------------+  +----------------+

                    OpenTelemetry
                           |
                           v
                +----------------------+
                |       SigNoz         |
                | Logs and Traces      |
                +----------+-----------+
                           |
                           v
                +----------------------+
                |   AI SRE Agent       |
                | Gemini + 3 Tools     |
                +----------+-----------+
                           |
                           v
                 Diagnosis and Next Steps
```

### Components

| Component | Responsibility |
|---|---|
| `frontend_service.py` | Handles incoming checkout requests and calls the order service. |
| `order_service.py` | Coordinates inventory and simulated AI calls; introduces latency and transaction failures. |
| `inventory_service.py` | Simulates inventory database latency and occasional connection-pool exhaustion. |
| `agent_service.py` | Simulates an application's AI dependency, including slow responses and malformed outputs. |
| `agent_diagnose.py` | Runs the Gemini-powered investigation using live SigNoz data. |
| `diagnose.py` | Provides an earlier, fixed-query diagnostic workflow. |
| `monitor.py` | Periodically checks error traces and launches the diagnostic agent when its threshold is reached. |
| `json_logger.py` | Provides structured JSON logging for service events. |
| `load_test.py` | Generates checkout traffic to exercise the microservices and produce telemetry. |

## How the AI investigation works

The diagnostic agent uses Gemini function calling and exposes three read-only tools.

| Tool | Purpose |
|---|---|
| `get_slow_traces()` | Retrieves the slowest root-level traces within a lookback window. |
| `get_error_logs()` | Retrieves recent error-level logs, optionally scoped to a service. |
| `get_error_traces()` | Retrieves traces containing error spans. |

The investigation follows an evidence-gathering loop:

1. **Investigate:** Gemini receives the investigation objective and available tools.
2. **Select:** The model chooses a tool and its arguments.
3. **Collect:** Python executes the selected tool against the SigNoz query API.
4. **Evaluate:** The results are returned to Gemini for interpretation.
5. **Continue or diagnose:** The model can request further evidence or provide its diagnosis.

The loop has a configurable maximum number of steps to prevent unbounded investigations.

The agent is instructed to explain what appears to be wrong, identify the most likely root cause when supported by evidence, and recommend a concrete next step. A diagnosis is still a model-generated hypothesis and should be validated by an engineer.

### Example investigation

Consider a checkout request that takes several seconds to complete.

- **Step 1 — Find the symptom:** Slow traces reveal unusually long checkout requests.
- **Step 2 — Narrow the investigation:** Error logs show that the frontend is waiting on a failing order-service request.
- **Step 3 — Recommend the next check:** The agent identifies the order service or one of its downstream dependencies as a likely cause and recommends examining the relevant error traces.

This is an illustrative investigation path. The actual sequence depends on the telemetry returned and the tools selected by the model.

## Observing the observer

A central design goal is making the AI investigation itself observable.

The diagnostic agent uses OpenTelemetry spans to represent the overall investigation, individual steps, Gemini requests, and tool executions.

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

The actual span tree depends on the investigation path and the number of tool calls.

The implementation records attributes such as:

- LLM provider and requested model
- Prompt, completion, and total token usage when returned by the API
- Investigation step and decision
- Tool name, arguments, and result count
- Tool execution and LLM request timing

These traces help answer two questions: *What went wrong in the application?* and *How did the diagnostic agent investigate it?*

## Demo results

The repository's documented demonstration run reported the following results from a load test captured in SigNoz.

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

The recorded trace showed that the final synthesis step accounted for approximately 40.78% of the total investigation duration.

These are results from the documented demonstration, not a guarantee of performance. Latency, success rates, and investigation paths depend on the simulated failures, telemetry, network, and LLM response times.

### Investigation trace

![SigNoz trace waterfall for an AI SRE investigation](trace-waterfall.png)

*Recorded SigNoz investigation trace showing the agent's execution and timing breakdown.*

## Technology stack

| Technology | Usage |
|---|---|
| Python | Application and agent implementation |
| FastAPI | Microservice APIs |
| HTTPX | HTTP communication between simulated services and load generation |
| Gemini API | LLM reasoning and function calling |
| SigNoz | Observability query platform and telemetry visualization |
| OpenTelemetry | Distributed tracing and AI execution instrumentation |
| Requests | HTTP requests to SigNoz and Gemini |
| python-dotenv | Local environment configuration |

## Getting started

### Prerequisites

Before starting, ensure you have:

- Python 3.10 or later
- A running SigNoz instance with its query API accessible
- Access to a Gemini API key through Google AI Studio
- The project dependencies installed
- An OTLP endpoint configured for sending telemetry to SigNoz

Docker may be used to run SigNoz, depending on your deployment. The application services are started separately as Python processes in this setup.

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

**macOS or Linux**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
python -m pip install opentelemetry-distro opentelemetry-exporter-otlp
opentelemetry-bootstrap -a install
```

If the requirements file does not yet include `requests` and `python-dotenv`, install those packages too:

```bash
python -m pip install requests python-dotenv
```

### 4. Configure environment variables

Create a local `.env` file in the repository root. Use the following template:

```dotenv
SIGNOZ_URL=http://localhost:8080
SIGNOZ_API_KEY=
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
MAX_AGENT_STEPS=5
LOOKBACK_MINUTES=15
```

Fill in your credentials locally. Use a SigNoz URL and credentials appropriate for your installation.

The diagnostic scripts read their configuration from environment variables, with `.env` loading supported by `python-dotenv`.

**Security requirements:**

- Never commit `.env` or real API keys to GitHub.
- Keep `.env.example` free of credentials.
- Rotate any credential that has been exposed.
- Keep your `.gitignore` configured to exclude local environment files.
- Remove exposed secrets from Git history when necessary; deleting them from the latest file alone is not sufficient.

### 5. Start SigNoz and the microservices

Make sure SigNoz is running and that its query endpoint and OTLP endpoint are reachable.

Open a separate terminal for each microservice. In each terminal, activate the virtual environment and set the OpenTelemetry endpoint and service name before starting the process.

**Example — Windows Command Prompt**

Frontend service:

```bat
set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
set OTEL_SERVICE_NAME=frontend-service
opentelemetry-instrument python frontend_service.py
```

Order service:

```bat
set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
set OTEL_SERVICE_NAME=order-service
opentelemetry-instrument python order_service.py
```

Inventory service:

```bat
set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
set OTEL_SERVICE_NAME=inventory-service
opentelemetry-instrument python inventory_service.py
```

Simulated AI service:

```bat
set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
set OTEL_SERVICE_NAME=agent-service
opentelemetry-instrument python agent_service.py
```

Adjust the OTLP endpoint to match your SigNoz installation. Each command should run in its own terminal and remain running.

### 6. Generate checkout traffic

Open another terminal and run:

```bash
python load_test.py
```

The traffic generator repeatedly sends checkout requests. The simulated services introduce variable latency and occasional failures so that SigNoz receives telemetry to investigate.

Allow some traffic to accumulate before running the diagnosis agent.

### 7. Run the AI SRE agent

Open another terminal, activate your environment, and execute:

```bat
set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
set OTEL_SERVICE_NAME=diagnosis-agent
opentelemetry-instrument python agent_diagnose.py
```

The agent queries SigNoz, asks Gemini to select investigation tools, executes those tools, and prints its final diagnosis.

To run the earlier fixed-query version instead:

```bash
python diagnose.py
```

### 8. Run the monitoring prototype

The repository also includes a continuous monitoring loop:

```bat
set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
set OTEL_SERVICE_NAME=diagnosis-agent
opentelemetry-instrument python monitor.py
```

The current monitor configuration checks every 60 seconds, evaluates error traces over a five-minute window, triggers an investigation at a threshold of three returned error-trace rows, and applies a three-minute cooldown after a trigger.

These are prototype thresholds, not production alerting guarantees. The monitoring logic should be improved to count distinct traces and handle investigation failures reliably before being used in a production environment.

## Project structure

```text
signoz-ai-sre-agent/
├── frontend_service.py
├── order_service.py
├── inventory_service.py
├── agent_service.py
├── agent_diagnose.py
├── diagnose.py
├── monitor.py
├── json_logger.py
├── load_test.py
├── requirements.txt
├── .gitignore
├── .env.example
├── SECURITY.md
├── trace-waterfall.png
└── README.md
```

The `.env` file is intentionally excluded from the repository and should exist only in your local environment or an appropriately secured deployment environment.

## Current limitations

This project is a prototype intended for learning, experimentation, and demonstration.

- The current diagnostic tools query logs and traces; they do not yet provide a dedicated metrics-investigation tool.
- The microservices use randomized failure injection rather than a real production database or external AI dependency.
- The root-cause analysis is an LLM-generated diagnosis and may be incomplete or incorrect.
- The monitoring implementation uses a basic threshold and cooldown rather than a fully developed alert-management system.
- The agent recommends next steps but does not automatically remediate incidents.
- The project requires reliable access to SigNoz and the Gemini API.

## Roadmap

- [ ] Improve monitoring reliability, error handling, and distinct-trace counting.
- [ ] Add richer and more reproducible failure scenarios.
- [ ] Generate structured incident reports with supporting evidence.
- [ ] Add dedicated metrics analysis and service-level objective context.
- [ ] Explore integrating the SigNoz MCP server as an alternative to handwritten query tools.
- [ ] Evaluate multi-agent investigation for logs, traces, and metrics.
- [ ] Add automated tests and continuous integration.
- [ ] Package the services into a reproducible deployment using container orchestration.
- [ ] Evaluate diagnosis quality against known failure scenarios.

## Lessons learned

Building this project highlighted that an effective AI agent needs more than an LLM and a prompt. It needs useful tools, reliable telemetry, well-defined failure scenarios, bounded execution, and visibility into its own behavior.

Working through service networking, SigNoz setup, OpenTelemetry configuration, and telemetry queries also demonstrated how much of real-world SRE engineering involves infrastructure and evidence gathering rather than simply interpreting an error message.

The project's central idea is straightforward: **make the investigation observable, not just the incident.**

## Contributing

Ideas, bug reports, and improvements are welcome.

For substantial changes, open an issue first so the proposed work can be discussed before implementation.

## License

This project is licensed under the MIT License, as indicated by the repository's badge. Ensure that a corresponding `LICENSE` file is present in the repository.

---

<div align="center">

**Built solo for the Agents of SigNoz Hackathon — AI & Agent Observability track.**

If you find the project useful, consider giving the repository a ⭐.

[GitHub Repository](https://github.com/polikeybhuvan/signoz-ai-sre-agent)

</div>
