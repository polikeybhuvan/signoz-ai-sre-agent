
import os
import time
import datetime

from dotenv import load_dotenv
from agent_diagnose import tool_get_error_traces, run_agent

# ------------------ CONFIG ------------------

load_dotenv()

CHECK_INTERVAL_SECONDS = 60
COOLDOWN_AFTER_ALERT_SECONDS = 180
ERROR_TRACE_THRESHOLD = 3
LOOKBACK_MINUTES_FOR_CHECK = 5

ALERT_LOG_FILE = "alerts.log"


# ------------------ ALERT LOGGING ------------------

def log_alert(text):
    timestamp = datetime.datetime.now().astimezone().isoformat(
        timespec="seconds"
    )

    with open(ALERT_LOG_FILE, "a", encoding="utf-8") as file:
        file.write(f"\n{'=' * 70}\n")
        file.write(f"ALERT TRIGGERED AT: {timestamp}\n")
        file.write(f"{'=' * 70}\n")
        file.write(text + "\n")


# ------------------ HEALTH CHECK ------------------

def check_health():
    """
    Count distinct trace IDs in the error-trace results,
    rather than counting every returned error span as a trace.
    """
    error_traces = tool_get_error_traces(
        lookback_minutes=LOOKBACK_MINUTES_FOR_CHECK
    )

    trace_ids = {
        str(trace["trace_id"])
        for trace in error_traces
        if trace.get("trace_id")
    }

    return len(trace_ids)


# ------------------ INVESTIGATION ------------------

def investigate_and_log():
    """
    Run the agent and log a diagnosis if one is returned.
    Report failures without terminating the monitoring loop.
    """
    try:
        diagnosis = run_agent()

        if not diagnosis:
            print(
                "Investigation did not produce a diagnosis. "
                "The monitor will continue."
            )
            return

        try:
            log_alert(diagnosis)
            print(f"Diagnosis logged to {ALERT_LOG_FILE}")

        except OSError as error:
            print(f"Could not write alert log: {error}")

    except Exception as error:
        print(
            "Investigation failed: "
            f"{type(error).__name__}: {error}"
        )


# ------------------ MONITOR LOOP ------------------

def main():
    print("=" * 70)
    print("  AI SRE Agent - Continuous Monitor")
    print(
        f"  Check interval: {CHECK_INTERVAL_SECONDS}s | "
        f"Threshold: {ERROR_TRACE_THRESHOLD} distinct traces / "
        f"{LOOKBACK_MINUTES_FOR_CHECK} min"
    )
    print("  Press Ctrl+C to stop.")
    print("=" * 70)

    while True:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        try:
            error_count = check_health()

        except Exception as error:
            print(
                f"[{timestamp}] Health check failed: "
                f"{type(error).__name__}: {error}"
            )
            time.sleep(CHECK_INTERVAL_SECONDS)
            continue

        if error_count >= ERROR_TRACE_THRESHOLD:
            print(
                f"\n[{timestamp}] ISSUE DETECTED: "
                f"{error_count} distinct error traces in the "
                f"last {LOOKBACK_MINUTES_FOR_CHECK} minutes."
            )

            print("Launching AI investigation...\n")
            investigate_and_log()

            print(
                f"\nCooling down for "
                f"{COOLDOWN_AFTER_ALERT_SECONDS}s..."
            )
            time.sleep(COOLDOWN_AFTER_ALERT_SECONDS)

        else:
            print(
                f"[{timestamp}] Healthy - "
                f"{error_count} distinct error traces in the "
                f"last {LOOKBACK_MINUTES_FOR_CHECK} minutes."
            )
            time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitor stopped by user.")
