
import os
import json
import time
import re
import requests

from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

# ------------------ CONFIG ------------------

load_dotenv()

SIGNOZ_URL = os.getenv(
    "SIGNOZ_URL",
    "http://localhost:8080"
).rstrip("/")

SIGNOZ_API_KEY = os.getenv("SIGNOZ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash"
)

MAX_AGENT_STEPS = max(
    1,
    int(os.getenv("MAX_AGENT_STEPS", "5"))
)

REQUEST_TIMEOUT = 15
GEMINI_TIMEOUT = 30

tracer = trace.get_tracer("diagnosis-agent")


def validate_credentials():
    missing = []

    if not SIGNOZ_API_KEY:
        missing.append("SIGNOZ_API_KEY")

    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")

    if missing:
        raise RuntimeError(
            "Missing environment variables: "
            + ", ".join(missing)
            + ". Configure them in your local .env file."
        )


# ------------------ SIGNOZ QUERY HELPERS ------------------

def _query_signoz(payload):
    validate_credentials()

    url = f"{SIGNOZ_URL}/api/v5/query_range"

    headers = {
        "Authorization": f"Bearer {SIGNOZ_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()
    return response.json()


def _extract_rows(response):
    try:
        return response["data"]["data"]["results"][0]["rows"]
    except (KeyError, IndexError, TypeError):
        return []


def _time_range(lookback_minutes):
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (lookback_minutes * 60 * 1000)
    return start_ms, now_ms


# ------------------ TOOLS THE AGENT CAN CALL ------------------

def tool_get_error_logs(lookback_minutes=15, service_name=None):
    start_ms, end_ms = _time_range(lookback_minutes)

    expression = "severity_text = 'ERROR'"

    if service_name:
        # Restrict service names to avoid malformed query expressions.
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", service_name):
            raise ValueError("Invalid service_name")

        expression += (
            f" AND resource.service.name = '{service_name}'"
        )

    payload = {
        "start": start_ms,
        "end": end_ms,
        "requestType": "raw",
        "compositeQuery": {
            "queries": [{
                "type": "builder_query",
                "spec": {
                    "name": "A",
                    "signal": "logs",
                    "filter": {"expression": expression},
                    "order": [{
                        "key": {"name": "timestamp"},
                        "direction": "desc"
                    }],
                    "offset": 0,
                    "limit": 20,
                    "disabled": False
                }
            }]
        }
    }

    rows = _extract_rows(_query_signoz(payload))
    output = []

    for row in rows[:15]:
        data = row.get("data", {})

        output.append({
            "service": data.get(
                "resources_string", {}
            ).get("service.name"),
            "body": data.get("body"),
            "status": data.get(
                "attributes_number", {}
            ).get("status"),
            "duration_ms": data.get(
                "attributes_number", {}
            ).get("duration_ms")
        })

    return output


def tool_get_slow_traces(lookback_minutes=15):
    start_ms, end_ms = _time_range(lookback_minutes)

    payload = {
        "start": start_ms,
        "end": end_ms,
        "requestType": "raw",
        "compositeQuery": {
            "queries": [{
                "type": "builder_query",
                "spec": {
                    "name": "A",
                    "signal": "traces",
                    "filter": {
                        "expression": "parentSpanID = ''"
                    },
                    "selectFields": [
                        {"name": "serviceName"},
                        {"name": "name"},
                        {"name": "durationNano"},
                        {"name": "traceID"}
                    ],
                    "order": [{
                        "key": {"name": "durationNano"},
                        "direction": "desc"
                    }],
                    "offset": 0,
                    "limit": 10,
                    "disabled": False
                }
            }]
        }
    }

    rows = _extract_rows(_query_signoz(payload))
    output = []

    for row in rows[:10]:
        data = row.get("data", {})
        duration_ns = data.get("durationNano") or 0

        output.append({
            "service": data.get("serviceName"),
            "operation": data.get("name"),
            "duration_ms": round(duration_ns / 1_000_000, 1),
            "trace_id": data.get("traceID")
        })

    return output


def tool_get_error_traces(lookback_minutes=15):
    start_ms, end_ms = _time_range(lookback_minutes)

    payload = {
        "start": start_ms,
        "end": end_ms,
        "requestType": "raw",
        "compositeQuery": {
            "queries": [{
                "type": "builder_query",
                "spec": {
                    "name": "A",
                    "signal": "traces",
                    "filter": {
                        "expression": "hasError = true"
                    },
                    "selectFields": [
                        {"name": "serviceName"},
                        {"name": "name"},
                        {"name": "traceID"}
                    ],
                    "order": [{
                        "key": {"name": "timestamp"},
                        "direction": "desc"
                    }],
                    "offset": 0,
                    "limit": 20,
                    "disabled": False
                }
            }]
        }
    }

    rows = _extract_rows(_query_signoz(payload))
    output = []

    for row in rows[:15]:
        data = row.get("data", {})

        output.append({
            "service": data.get("serviceName"),
            "operation": data.get("name"),
            "trace_id": data.get("traceID")
        })

    return output


# ------------------ TOOL REGISTRY ------------------

TOOL_IMPLEMENTATIONS = {
    "get_error_logs": tool_get_error_logs,
    "get_slow_traces": tool_get_slow_traces,
    "get_error_traces": tool_get_error_traces
}


TOOL_DECLARATIONS = [
    {
        "name": "get_error_logs",
        "description": (
            "Fetch recent ERROR-level structured logs from SigNoz, "
            "optionally filtered to one service. Use this to inspect "
            "actual error messages."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lookback_minutes": {
                    "type": "integer",
                    "description": (
                        "How many minutes back to search. Default 15."
                    }
                },
                "service_name": {
                    "type": "string",
                    "description": (
                        "Optional service filter, e.g. order-service."
                    )
                }
            }
        }
    },
    {
        "name": "get_slow_traces",
        "description": (
            "Fetch the slowest root-level traces across all services "
            "in the last N minutes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lookback_minutes": {
                    "type": "integer",
                    "description": (
                        "How many minutes back to search. Default 15."
                    )
                }
            }
        }
    },
    {
        "name": "get_error_traces",
        "description": (
            "Fetch traces containing at least one error span, "
            "showing the services and operations involved."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lookback_minutes": {
                    "type": "integer",
                    "description": (
                        "How many minutes back to search. Default 15."
                    )
                }
            }
        }
    }
]


# ------------------ GEMINI API ------------------

def call_gemini(contents):
    validate_credentials()

    with tracer.start_as_current_span(
        "gemini.generate_content"
    ) as span:

        span.set_attribute("gen_ai.system", "gemini")
        span.set_attribute("gen_ai.request.model", GEMINI_MODEL)

        # Send the API key in a header, not in the URL.
        url = (
            "https://generativelanguage.googleapis.com/"
            f"v1beta/models/{GEMINI_MODEL}:generateContent"
        )

        headers = {
            "x-goog-api-key": GEMINI_API_KEY,
            "Content-Type": "application/json"
        }

        payload = {
            "contents": contents,
            "tools": [{
                "functionDeclarations": TOOL_DECLARATIONS
            }]
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=GEMINI_TIMEOUT
            )

            response.raise_for_status()
            result = response.json()

            usage = result.get("usageMetadata", {})

            span.set_attribute(
                "gen_ai.usage.prompt_tokens",
                usage.get("promptTokenCount", 0)
            )
            span.set_attribute(
                "gen_ai.usage.completion_tokens",
                usage.get("candidatesTokenCount", 0)
            )
            span.set_attribute(
                "gen_ai.usage.total_tokens",
                usage.get("totalTokenCount", 0)
            )

            return result

        except Exception as error:
            span.record_exception(error)
            span.set_status(
                Status(StatusCode.ERROR, str(error))
            )
            raise


# ------------------ TOOL EXECUTION ------------------

def run_tool(tool_name, tool_args):
    with tracer.start_as_current_span(
        f"agent.tool_call.{tool_name}"
    ) as span:

        span.set_attribute("tool.name", tool_name)

        for key, value in tool_args.items():
            span.set_attribute(
                f"tool.arg.{key}",
                str(value)
            )

        if tool_name not in TOOL_IMPLEMENTATIONS:
            error_message = f"Unknown tool: {tool_name}"

            span.set_status(
                Status(StatusCode.ERROR, error_message)
            )

            return {"error": error_message}

        try:
            result = TOOL_IMPLEMENTATIONS[tool_name](
                **tool_args
            )

            span.set_attribute(
                "tool.result_count",
                len(result) if isinstance(result, list) else 0
            )

            return result

        except Exception as error:
            span.set_status(
                Status(StatusCode.ERROR, str(error))
            )
            span.record_exception(error)

            return {
                "error": (
                    f"{type(error).__name__}: {error}"
                )
            }


# ------------------ AGENT INVESTIGATION LOOP ------------------

def run_agent():
    with tracer.start_as_current_span(
        "agent.investigation"
    ) as root_span:

        system_instruction = (
            "You are an SRE assistant investigating a microservices "
            "system (frontend-service -> order-service -> "
            "inventory-service, agent-service) using live SigNoz "
            "observability data. You have tools to fetch error logs, "
            "slow traces, and error traces. Investigate step by step: "
            "start broad, then narrow in on the services that appear "
            "most suspicious. Use tool results as evidence. "
            "Do not invent findings or claim certainty without "
            "supporting evidence. Once you have enough evidence, "
            "stop calling tools and provide a plain-English diagnosis "
            "covering: (1) what is going wrong, (2) the likely root "
            "cause service, (3) one concrete fix or next step, and "
            "(4) any uncertainty or missing evidence."
        )

        contents = [{
            "role": "user",
            "parts": [{
                "text": (
                    system_instruction
                    + "\n\nBegin your investigation now."
                )
            }]
        }]

        try:
            for step in range(1, MAX_AGENT_STEPS + 1):
                with tracer.start_as_current_span(
                    f"agent.step.{step}"
                ) as step_span:

                    print(f"\n--- Agent step {step} ---")

                    response = call_gemini(contents)
                    candidates = response.get("candidates", [])

                    if not candidates:
                        message = "Gemini returned no candidates."

                        print(message)
                        step_span.set_status(
                            Status(StatusCode.ERROR, message)
                        )
                        root_span.set_status(
                            Status(StatusCode.ERROR, message)
                        )
                        return None

                    candidate = candidates[0]
                    parts = candidate.get(
                        "content", {}
                    ).get("parts", [])

                    if not parts:
                        message = (
                            "Gemini returned no response parts."
                        )

                        print(message)
                        step_span.set_status(
                            Status(StatusCode.ERROR, message)
                        )
                        return None

                    # Preserve the model response for the next turn.
                    contents.append({
                        "role": "model",
                        "parts": parts
                    })

                    # A response can contain more than one function call.
                    function_calls = [
                        part["functionCall"]
                        for part in parts
                        if "functionCall" in part
                    ]

                    if function_calls:
                        step_responses = []

                        for function_call in function_calls:
                            tool_name = function_call["name"]
                            tool_args = function_call.get("args", {})

                            step_span.set_attribute(
                                "agent.decision",
                                f"call_tool:{tool_name}"
                            )

                            print(
                                f"Agent wants to call: "
                                f"{tool_name}({tool_args})"
                            )

                            tool_result = run_tool(
                                tool_name,
                                tool_args
                            )

                            print(
                                "Tool result (truncated): "
                                + json.dumps(tool_result)[:500]
                            )

                            step_responses.append({
                                "functionResponse": {
                                    "name": tool_name,
                                    "response": {
                                        "result": tool_result
                                    }
                                }
                            })

                        # Return all tool results in the next turn.
                        contents.append({
                            "role": "user",
                            "parts": step_responses
                        })

                        continue

                    text_parts = [
                        part["text"]
                        for part in parts
                        if isinstance(part.get("text"), str)
                    ]

                    if text_parts:
                        step_span.set_attribute(
                            "agent.decision",
                            "final_answer"
                        )

                        root_span.set_attribute(
                            "agent.total_steps",
                            step
                        )

                        final_text = "\n".join(text_parts)

                        print("\n===== FINAL AI DIAGNOSIS =====")
                        print(final_text)

                        return final_text

                    message = (
                        "Gemini returned neither a function call "
                        "nor a text diagnosis."
                    )

                    print(message)

                    step_span.set_status(
                        Status(StatusCode.ERROR, message)
                    )

                    return None

            message = (
                "Reached maximum agent steps without "
                "a final diagnosis."
            )

            print(f"\n{message}")

            root_span.set_status(
                Status(StatusCode.ERROR, message)
            )

            return None

        except Exception as error:
            root_span.record_exception(error)
            root_span.set_status(
                Status(StatusCode.ERROR, str(error))
            )

            print(
                "\nAgent investigation failed: "
                f"{type(error).__name__}: {error}"
            )

            return None


# ------------------ ENTRY POINT ------------------

if __name__ == "__main__":
    diagnosis = run_agent()

    if not diagnosis:
        raise SystemExit(1)
