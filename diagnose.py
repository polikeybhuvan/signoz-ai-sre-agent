import requests
import json
import time

# ------------------ CONFIG ------------------
SIGNOZ_URL = "http://localhost:8080"
SIGNOZ_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3ODQ0NjMwODMsImlhdCI6MTc4NDQ2MTI4MywiaWQiOiIwMTlmNzc0OC0yMmI5LTczMjctOTlhNC1kNjI1NThlMTg2YTMiLCJlbWFpbCI6InBvbGlrZXliaHV2YW5AZ21haWwuY29tIiwib3JnSWQiOiIwMTlmNzc0OC0yMmI5LTczMTctYThiOS1kNDVlMDRiMWVkOGMifQ.E0k-9VueFjNUaqYJhvDbImvGZZI7HROdhNiNaaXMD8A"
GEMINI_API_KEY = "AIzaSyD1Bejb6koUh4j5oBUATRa-Bj2ErnPgysk"

LOOKBACK_MINUTES = 15


def get_time_range():
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (LOOKBACK_MINUTES * 60 * 1000)
    return start_ms, now_ms


def query_signoz(payload):
    url = f"{SIGNOZ_URL}/api/v5/query_range"
    headers = {
        "Authorization": f"Bearer {SIGNOZ_API_KEY}",
        "Content-Type": "application/json"
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


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
                    "filter": {"expression": "severity_text = 'ERROR'"},
                    "order": [{"key": {"name": "timestamp"}, "direction": "desc"}],
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
                    "filter": {"expression": "parentSpanID = ''"},
                    "selectFields": [
                        {"name": "serviceName"},
                        {"name": "name"},
                        {"name": "durationNano"},
                        {"name": "traceID"}
                    ],
                    "order": [{"key": {"name": "durationNano"}, "direction": "desc"}],
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
                    "filter": {"expression": "hasError = true"},
                    "selectFields": [
                        {"name": "serviceName"},
                        {"name": "name"},
                        {"name": "durationNano"},
                        {"name": "traceID"}
                    ],
                    "order": [{"key": {"name": "timestamp"}, "direction": "desc"}],
                    "offset": 0,
                    "limit": 20,
                    "disabled": False
                }
            }]
        }
    }
    return query_signoz(payload)


def summarize_for_llm(error_logs, slow_traces, error_traces):
    summary = "=== RECENT ERROR LOGS ===\n"
    try:
        rows = error_logs["data"]["data"]["results"][0]["rows"]
        for row in rows[:15]:
            d = row.get("data", {})
            summary += (
                f"service={d.get('resources_string', {}).get('service.name')} "
                f"body={d.get('body')} "
                f"status={d.get('attributes_number', {}).get('status')} "
                f"duration_ms={d.get('attributes_number', {}).get('duration_ms')}\n"
            )
    except (KeyError, IndexError, TypeError):
        summary += "(none found or unexpected format)\n"

    summary += "\n=== SLOWEST ROOT TRACES ===\n"
    try:
        rows = slow_traces["data"]["data"]["results"][0]["rows"]
        for row in rows[:10]:
            d = row.get("data", {})
            summary += f"service={d.get('serviceName')} op={d.get('name')} duration_ns={d.get('durationNano')} traceID={d.get('traceID')}\n"
    except (KeyError, IndexError, TypeError):
        summary += "(none found or unexpected format)\n"

    summary += "\n=== TRACES WITH ERRORS ===\n"
    try:
        rows = error_traces["data"]["data"]["results"][0]["rows"]
        for row in rows[:15]:
            d = row.get("data", {})
            summary += f"service={d.get('serviceName')} op={d.get('name')} traceID={d.get('traceID')}\n"
    except (KeyError, IndexError, TypeError):
        summary += "(none found or unexpected format)\n"

    return summary


def ask_gemini(context_summary):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

    prompt = f"""You are an SRE assistant analyzing observability data from SigNoz for a
microservices system (frontend-service -> order-service -> inventory-service,
agent-service). Based on the data below, write a short, plain-English diagnosis:
1) What is currently going wrong (if anything)
2) Which service is most likely the root cause
3) One concrete suggestion to investigate or fix it

DATA:
{context_summary}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    return result["candidates"][0]["content"]["parts"][0]["text"]


def main():
    start_ms, end_ms = get_time_range()
    print(f"Fetching last {LOOKBACK_MINUTES} minutes of data from SigNoz...\n")

    error_logs = fetch_error_logs(start_ms, end_ms)
    slow_traces = fetch_slow_traces(start_ms, end_ms)
    error_traces = fetch_error_traces(start_ms, end_ms)

    context_summary = summarize_for_llm(error_logs, slow_traces, error_traces)
    print("----- Raw data pulled from SigNoz -----")
    print(context_summary)

    print("----- Asking Gemini for diagnosis... -----\n")
    diagnosis = ask_gemini(context_summary)
    print("===== AI DIAGNOSIS =====")
    print(diagnosis)


if __name__ == "__main__":
    main()