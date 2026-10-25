
import os
import time
import requests
from dotenv import load_dotenv

# ------------------ CONFIG ------------------

# Load local environment variables from .env
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

LOOKBACK_MINUTES = int(
    os.getenv("LOOKBACK_MINUTES", "15")
)

SIGNOZ_TIMEOUT = 15
GEMINI_TIMEOUT = 30

if not SIGNOZ_API_KEY or not GEMINI_API_KEY:
    raise RuntimeError(
        "Missing API credentials. Configure SIGNOZ_API_KEY "
        "and GEMINI_API_KEY in your local .env file."
    )


# ------------------ TIME RANGE ------------------

def get_time_range():
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - LOOKBACK_MINUTES * 60 * 1000
    return start_ms, now_ms


# ------------------ SIGNOZ API ------------------

def query_signoz(payload):
    url = f"{SIGNOZ_URL}/api/v5/query_range"

    headers = {
        "Authorization": f"Bearer {SIGNOZ_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=SIGNOZ_TIMEOUT
    )

    response.raise_for_status()
    return response.json()


def fetch_error_logs(start_ms, end_ms):
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
                    "filter": {
                        "expression": "severity_text = 'ERROR'"
                    },
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

    return query_signoz(payload)


def fetch_slow_traces(start_ms, end_ms):
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

    return query_signoz(payload)


def fetch_error_traces(start_ms, end_ms):
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
                        {"name": "durationNano"},
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

    return query_signoz(payload)


# ------------------ EXTRACT RESULTS ------------------

def extract_rows(response):
    try:
        return response["data"]["data"]["results"][0]["rows"]
    except (KeyError, IndexError, TypeError):
        return []


# ------------------ SUMMARIZE OBSERVABILITY DATA ------------------

def summarize_for_llm(error_logs, slow_traces, error_traces):
    lines = ["=== RECENT ERROR LOGS ==="]

    rows = extract_rows(error_logs)

    if not rows:
        lines.append("(No error logs found or unexpected response format)")

    for row in rows[:15]:
        data = row.get("data", {})

        service = data.get("resources_string", {}).get(
            "service.name"
        )
        body = data.get("body")
        status = data.get("attributes_number", {}).get("status")
        duration = data.get("attributes_number", {}).get(
            "duration_ms"
        )

        lines.append(
            f"service={service} "
            f"body={body} "
            f"status={status} "
            f"duration_ms={duration}"
        )

    lines.append("\n=== SLOWEST ROOT TRACES ===")

    rows = extract_rows(slow_traces)

    if not rows:
        lines.append("(No slow traces found or unexpected response format)")

    for row in rows[:10]:
        data = row.get("data", {})

        lines.append(
            f"service={data.get('serviceName')} "
            f"op={data.get('name')} "
            f"duration_ns={data.get('durationNano')} "
            f"traceID={data.get('traceID')}"
        )

    lines.append("\n=== TRACES WITH ERRORS ===")

    rows = extract_rows(error_traces)

    if not rows:
        lines.append("(No error traces found or unexpected response format)")

    for row in rows[:15]:
        data = row.get("data", {})

        lines.append(
            f"service={data.get('serviceName')} "
            f"op={data.get('name')} "
            f"traceID={data.get('traceID')}"
        )

    return "\n".join(lines)


# ------------------ GEMINI API ------------------

def ask_gemini(context_summary):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{GEMINI_MODEL}:generateContent"
    )

    # Send the API key in a header, not in the URL.
    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json"
    }

    prompt = f"""
You are an SRE assistant analyzing observability data from
SigNoz for this microservices system:

frontend-service -> order-service -> inventory-service
agent-service

Use the supplied evidence to produce a concise, plain-English
diagnosis covering:

1. What appears to be going wrong.
2. Which service is the likely root cause, if the evidence
   supports identifying one.
3. One concrete next step or possible fix.
4. Your confidence and any missing evidence.

Do not invent evidence. Distinguish observed symptoms from
confirmed root causes. If the data is insufficient, say so.

OBSERVABILITY DATA:
{context_summary}
"""

    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt}]
        }]
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=GEMINI_TIMEOUT
    )

    response.raise_for_status()

    result = response.json()
    candidates = result.get("candidates", [])

    if not candidates:
        raise RuntimeError(
            "Gemini returned no candidates. The response may "
            "have been blocked or may not contain a diagnosis."
        )

    parts = candidates[0].get("content", {}).get("parts", [])

    text_parts = [
        part["text"]
        for part in parts
        if isinstance(part.get("text"), str)
    ]

    if not text_parts:
        raise RuntimeError(
            "Gemini returned no text in its response."
        )

    return "\n".join(text_parts)


# ------------------ MAIN ------------------

def main():
    print(
        f"Fetching the last {LOOKBACK_MINUTES} minutes "
        "of data from SigNoz...\n"
    )

    start_ms, end_ms = get_time_range()

    try:
        error_logs = fetch_error_logs(start_ms, end_ms)
        slow_traces = fetch_slow_traces(start_ms, end_ms)
        error_traces = fetch_error_traces(start_ms, end_ms)

        context_summary = summarize_for_llm(
            error_logs,
            slow_traces,
            error_traces
        )

        print("----- Observability data -----")
        print(context_summary)

        print("\n----- Asking Gemini for diagnosis -----\n")

        diagnosis = ask_gemini(context_summary)

        print("===== AI DIAGNOSIS =====")
        print(diagnosis)

    except requests.exceptions.Timeout:
        print(
            "Request timed out. Check your network connection, "
            "SigNoz endpoint, and API availability."
        )
        raise

    except requests.exceptions.HTTPError as exc:
        status = (
            exc.response.status_code
            if exc.response is not None
            else "unknown"
        )
        print(
            f"API request failed with HTTP status {status}. "
            "Check your credentials, endpoint, permissions, "
            "and request parameters."
        )
        raise

    except requests.exceptions.RequestException:
        print(
            "Network request failed. Check connectivity and "
            "the service endpoint."
        )
        raise


if __name__ == "__main__":
    main()
