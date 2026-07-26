import asyncio
import random
import time
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# Import our custom JSON logger
from json_logger import setup_logger

app = FastAPI(title="Inventory Service")
logger = setup_logger("inventory_service", "inventory-service")

@app.get("/stock")
async def check_stock(x_request_id: str = Header(default=None)):
    """
    Simulates checking warehouse and stock database levels.
    Injects a realistic slow-query simulation and a service outage rate.
    """
    request_id = x_request_id or "unknown-request"
    start_time = time.time()
    
    # ------------------ DELAY INJECTION ------------------
    # Simulates a slow DB lookup: random delay 50 - 1200ms
    delay = random.uniform(0.05, 1.2)
    logger.info(
        f"Retrieving stock status from inventory DB replica. Query delay: {int(delay * 1000)}ms",
        extra={"request_id": request_id, "query_delay_ms": int(delay * 1000)}
    )
    await asyncio.sleep(delay)
    
    # ------------------ FAILURE INJECTION ------------------
    # 1 in 12 requests returns 503 Service Unavailable (database pool exhaustion simulation)
    if random.randint(1, 12) == 1:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "DATABASE POOL ERROR: DB connection limit exceeded. Refusing connection.",
            extra={"request_id": request_id, "status": 503, "duration_ms": duration_ms}
        )
        return JSONResponse(
            status_code=503,
            content={
                "error": "Service Unavailable",
                "message": "Database replica pool exhausted. Please retry.",
                "request_id": request_id
            }
        )
        
    duration_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "Stock verification completed. DB query returned successfully.",
        extra={
            "request_id": request_id,
            "status": 200,
            "duration_ms": duration_ms
        }
    )
    
    return {
        "items": [
            {"sku": "AI-AGNT-01", "available": True, "quantity": 42},
            {"sku": "OTEL-SIGN-99", "available": True, "quantity": 1337}
        ],
        "warehouse_zone": "us-east-1a",
        "duration_ms": duration_ms
    }

if __name__ == "__main__":
    print("Starting inventory-service on port 8003...")
    uvicorn.run("inventory_service:app", host="0.0.0.0", port=8003, log_level="warning")
