import time
import random
import httpx
import sys

# Color codes for clean console feedback
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

TARGET_URL = "http://localhost:8001/checkout"

def run_load_test():
    print(f"{YELLOW}========================================================")
    print(f"  OTel Observability Load Generator Starting...  ")
    print(f"  Target: {TARGET_URL}")
    print(f"  Interval: 1-2s (randomized jitter)")
    print(f"  Press Ctrl+C to terminate.")
    print(f"========================================================{RESET}\n")
    
    success_count = 0
    fail_count = 0
    total_count = 0
    
    with httpx.Client() as client:
        while True:
            total_count += 1
            start_time = time.time()
            
            try:
                # Fire the request
                response = client.get(TARGET_URL, timeout=15.0)
                duration = time.time() - start_time
                
                if response.status_code == 200:
                    success_count += 1
                    data = response.json()
                    req_id = data.get("request_id", "unknown")
                    # Pull latency from response
                    inner_latency = data.get("duration_ms", 0)
                    print(
                        f"{GREEN}[SUCCESS]{RESET} Request #{total_count} "
                        f"| Total Latency: {int(duration*1000)}ms | CallChain Latency: {inner_latency}ms "
                        f"| ReqID: {req_id}"
                    )
                else:
                    fail_count += 1
                    print(
                        f"{YELLOW}[WARN]{RESET} Request #{total_count} "
                        f"| Returned Status Code: {response.status_code} "
                        f"| Total Latency: {int(duration*1000)}ms"
                    )
                    
            except httpx.RequestError as exc:
                fail_count += 1
                duration = time.time() - start_time
                print(
                    f"{RED}[FAIL]{RESET} Request #{total_count} "
                    f"| HTTP connection failed: {exc.__class__.__name__} "
                    f"| Elapsed: {int(duration*1000)}ms"
                )
                
            # Print periodic health summaries every 15 cycles
            if total_count % 15 == 0:
                print(
                    f"\n--- {YELLOW}LOAD GENERATOR STATUS SUMMARY{RESET} ---"
                    f"\n  Total Attempts : {total_count}"
                    f"\n  Successful     : {GREEN}{success_count}{RESET}"
                    f"\n  Failed / Flaky : {RED}{fail_count}{RESET}"
                    f"\n  Success Rate   : {(success_count/total_count)*100:.2f}%"
                    f"\n-----------------------------------------\n"
                )
                
            # Random jitter sleep (1.0 to 2.5 seconds)
            sleep_time = random.uniform(1.0, 2.5)
            time.sleep(sleep_time)

if __name__ == "__main__":
    try:
        run_load_test()
    except KeyboardInterrupt:
        print(f"\n{RED}Load test terminated by user. Exiting gracefully.{RESET}")
        sys.exit(0)
