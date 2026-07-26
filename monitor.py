import time
import datetime
from agent_diagnose import tool_get_error_traces, run_agent

CHECK_INTERVAL_SECONDS = 60
COOLDOWN_AFTER_ALERT_SECONDS = 180
ERROR_TRACE_THRESHOLD = 3
LOOKBACK_MINUTES_FOR_CHECK = 5

ALERT_LOG_FILE = "alerts.log"


def log_alert(text):
    timestamp = datetime.datetime.now().isoformat(timespec="seconds")
    with open(ALERT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"ALERT TRIGGERED AT: {timestamp}\n")
        f.write(f"{'='*70}\n")
        f.write(text + "\n")


def check_health():
    error_traces = tool_get_error_traces(lookback_minutes=LOOKBACK_MINUTES_FOR_CHECK)
    return len(error_traces)


def main():
    print("=" * 70)
    print("  Continuous SRE Monitor Starting...")
    print(f"  Checking every {CHECK_INTERVAL_SECONDS}s | "
          f"threshold: {ERROR_TRACE_THRESHOLD} error traces / "
          f"{LOOKBACK_MINUTES_FOR_CHECK} min")
    print("  Press Ctrl+C to stop.")
    print("=" * 70)

    while True:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        try:
            error_count = check_health()
        except Exception as e:
            print(f"[{timestamp}] Health check failed: {e}")
            time.sleep(CHECK_INTERVAL_SECONDS)
            continue

        if error_count >= ERROR_TRACE_THRESHOLD:
            print(f"\n[{timestamp}] *** ISSUE DETECTED *** "
                  f"({error_count} error traces in last {LOOKBACK_MINUTES_FOR_CHECK} min)")
            print("Launching full AI investigation...\n")
            diagnosis = run_agent()
            if diagnosis:
                log_alert(diagnosis)
                print(f"\n[{timestamp}] Alert logged to {ALERT_LOG_FILE}")
            print(f"\nCooling down for {COOLDOWN_AFTER_ALERT_SECONDS}s before next check...")
            time.sleep(COOLDOWN_AFTER_ALERT_SECONDS)
        else:
            print(f"[{timestamp}] Healthy — {error_count} error traces in last "
                  f"{LOOKBACK_MINUTES_FOR_CHECK} min")
            time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()