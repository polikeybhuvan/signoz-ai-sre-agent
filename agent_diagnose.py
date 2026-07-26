import requests
import json
import time

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer("diagnosis-agent")

# ------------------ CONFIG ------------------
SIGNOZ_URL = "http://localhost:8080"
SIGNOZ_API_KEY = "YOUR_SIGNOZ_JWT_OR_API_KEY_HERE"
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE"

MAX_AGENT_STEPS = 5


# ------------------ SIGNOZ QUERY HELPERS ------------------

def _query_signoz(payload):
    url = f"{SIGNOZ_URL}/api/v5/query_range"
    headers = {
        "Authorization": f"Bearer {SIGNOZ_API_KEY}",
        "Content-Type": "application/json"
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


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
    expr = "severity_text = 'ERROR'"
    if service_name:
        expr += f" AND resource.service.name = '{service_name}'"
    payload = {
        "start": start_ms, "end": end_ms, "requestType": "raw",
        "compositeQuery": {"queries": [{
            "type": "builder_query",
            "spec": {
                "name": "A", "signal": "logs",
                "filter": {"expression": expr},
                "order": [{"key": {"name": "timestamp"}, "direction": "desc"}],
                "offset": 0, "limit": 20, "disabled": False
            }
        }]}
    }
    rows = _extract_rows(_query_signoz(payload))
    out = []
    for row in rows[:15]:
        d = row.get("data", {})
        out.append({
            "service": d.get("resources_string", {}).get("service.name"),
            "body": d.get("body"),
            "status": d.get("attributes_number", {}).get("status"),
            "duration_ms": d.get("attributes_number", {}).get("duration_ms"),
        })
    return out


def tool_get_slow_traces(lookback_minutes=15):
    start_ms, end_ms = _time_range(lookback_minutes)
    payload = {
        "start": start_ms, "end": end_ms, "requestType": "raw",
        "compositeQuery": {"queries": [{
            "type": "builder_query",
            "spec": {
                "name": "A", "signal": "traces",
                "filter": {"expression": "parentSpanID = ''"},
                "selectFields": [
                    {"name": "serviceName"}, {"name": "name"},
                    {"name": "durationNano"}, {"name": "traceID"}
                ],
                "order": [{"key": {"name": "durationNano"}, "direction": "desc"}],
                "offset": 0, "limit": 10, "disabled": False
            }
        }]}
    }
    rows = _extract_rows(_query_signoz(payload))
    out = []
    for row in rows[:10]:
        d = row.get("data", {})
        out.append({
            "service": d.get("serviceName"),
            "operation": d.get("name"),
            "duration_ms": round((d.get("durationNano") or 0) / 1_000_000, 1),
            "trace_id": d.get("traceID"),
        })
    return out


def tool_get_error_traces(lookback_minutes=15):
    start_ms, end_ms = _time_range(lookback_minutes)
    payload = {
        "start": start_ms, "end": end_ms, "requestType": "raw",
        "compositeQuery": {"queries": [{
            "type": "builder_query",
            "spec": {
                "name": "A", "signal": "traces",
                "filter": {"expression": "hasError = true"},
                "selectFields": [
                    {"name": "serviceName"}, {"name": "name"}, {"name": "traceID"}
                ],
                "order": [{"key": {"name": "timestamp"}, "direction": "desc"}],
                "offset": 0, "limit": 20, "disabled": False
            }
        }]}
    }
    rows = _extract_rows(_query_signoz(payload))
    out = []
    for row in rows[:15]:
        d = row.get("data", {})
        out.append({
            "service": d.get("serviceName"),
            "operation": d.get("name"),
            "trace_id": d.get("traceID"),
        })
    return out


TOOL_IMPLEMENTATIONS = {
    "get_error_logs": tool_get_error_logs,
    "get_slow_traces": tool_get_slow_traces,
    "get_error_traces": tool_get_error_traces,
}

TOOL_DECLARATIONS = [
    {
        "name": "get_error_logs",
        "description": "Fetch recent ERROR-level structured logs from SigNoz, optionally filtered to one service. Use this to see the actual error messages.",
        "parameters": {
            "type": "object",
            "properties": {
                "lookback_minutes": {"type": "integer", "description": "How many minutes back to search. Default 15."},
                "service_name": {"type": "string", "description": "Optional: restrict to one service, e.g. 'order-service'."}
            }
        }
    },
    {
        "name": "get_slow_traces",
        "description": "Fetch the slowest root-level traces (full request latency) from SigNoz across all services in the last N minutes.",
        "parameters": {
            "type": "object",
            "properties": {
                "lookback_minutes": {"type": "integer", "description": "How many minutes back to search. Default 15."}
            }
        }
    },
    {
        "name": "get_error_traces",
        "description": "Fetch traces that contain at least one error span, showing which services and operations were involved in each failing request.",
        "parameters": {
            "type": "object",
            "properties": {
                "lookback_minutes": {"type": "integer", "description": "How many minutes back to search. Default 15."}
            }
        }
    },
]


# ------------------ GEMINI AGENT LOOP ------------------

def call_gemini(contents):
    with tracer.start_as_current_span("gemini.generate_content") as span:
        span.set_attribute("gen_ai.system", "gemini")
        span.set_attribute("gen_ai.request.model", "gemini-2.5-flash")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": contents,
            "tools": [{"functionDeclarations": TOOL_DECLARATIONS}]
        }
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()

        usage = result.get("usageMetadata", {})
        span.set_attribute("gen_ai.usage.prompt_tokens", usage.get("promptTokenCount", 0))
        span.set_attribute("gen_ai.usage.completion_tokens", usage.get("candidatesTokenCount", 0))
        span.set_attribute("gen_ai.usage.total_tokens", usage.get("totalTokenCount", 0))

        return result


def run_tool(tool_name, tool_args):
    with tracer.start_as_current_span(f"agent.tool_call.{tool_name}") as span:
        span.set_attribute("tool.name", tool_name)
        for k, v in tool_args.items():
            span.set_attribute(f"tool.arg.{k}", str(v))

        if tool_name not in TOOL_IMPLEMENTATIONS:
            span.set_status(Status(StatusCode.ERROR, "unknown tool"))
            return {"error": f"Unknown tool {tool_name}"}

        try:
            result = TOOL_IMPLEMENTATIONS[tool_name](**tool_args)
            span.set_attribute("tool.result_count", len(result) if isinstance(result, list) else 0)
            return result
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            return {"error": str(e)}


def run_agent():
    with tracer.start_as_current_span("agent.investigation") as root_span:
        system_instruction = (
            "You are an SRE assistant investigating a microservices system "
            "(frontend-service -> order-service -> inventory-service, agent-service) "
            "using live SigNoz observability data. You have tools to fetch error logs, "
            "slow traces, and error traces. Investigate step by step: start broad, then "
            "narrow in on whichever service looks most suspicious. Once you have enough "
            "evidence, STOP calling tools and give a final plain-English diagnosis covering: "
            "1) what is going wrong, 2) which service is the root cause, 3) one concrete "
            "fix or next investigation step."
        )

        contents = [
            {"role": "user", "parts": [{"text": system_instruction + "\n\nBegin your investigation now."}]}
        ]

        for step in range(1, MAX_AGENT_STEPS + 1):
            with tracer.start_as_current_span(f"agent.step.{step}") as step_span:
                print(f"\n--- Agent step {step} ---")
                response = call_gemini(contents)

                try:
                    candidate = response["candidates"][0]
                except (KeyError, IndexError):
                    print("No candidate returned. Raw response:", json.dumps(response, indent=2)[:1000])
                    step_span.set_status(Status(StatusCode.ERROR, "no candidate"))
                    return

                parts = candidate["content"]["parts"]
                contents.append({"role": "model", "parts": parts})

                function_call_part = None
                text_parts = []
                for part in parts:
                    if "functionCall" in part:
                        function_call_part = part["functionCall"]
                    elif "text" in part:
                        text_parts.append(part["text"])

                if function_call_part:
                    tool_name = function_call_part["name"]
                    tool_args = function_call_part.get("args", {})
                    step_span.set_attribute("agent.decision", f"call_tool:{tool_name}")
                    print(f"Agent wants to call: {tool_name}({tool_args})")

                    tool_result = run_tool(tool_name, tool_args)
                    print(f"Tool result (truncated): {json.dumps(tool_result)[:500]}")

                    contents.append({
                        "role": "user",
                        "parts": [{
                            "functionResponse": {
                                "name": tool_name,
                                "response": {"result": tool_result}
                            }
                        }]
                    })
                    continue

                if text_parts:
                    step_span.set_attribute("agent.decision", "final_answer")
                    root_span.set_attribute("agent.total_steps", step)
                    final_text = "\n".join(text_parts)
                    print("\n===== FINAL AI DIAGNOSIS =====")
                    print(final_text)
                    return final_text

        print("\nReached max agent steps without a final answer. Last response:")
        print(json.dumps(contents[-1], indent=2)[:1000])
        root_span.set_status(Status(StatusCode.ERROR, "max steps reached without final answer"))


if __name__ == "__main__":
    run_agent()
