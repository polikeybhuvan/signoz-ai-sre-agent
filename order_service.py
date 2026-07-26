import asyncio
import random
import time
import httpx
from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.responses import JSONResponse
import uvicorn

# Import our custom JSON logger
from json_logger import setup_logger

app = FastAPI(title="Order Service")
logger = setup_logger("order_service", "order-service")

# Downstream URLs
INVENTORY_SERVICE_URL = "http://localhost:8003/stock"
AGENT_SERVICE_URL = "http://localhost:8004/assist"

@app.get("/order")
async def process_order(x_request_id: str = Header(default=None)):
    """
    Simulates checking out and submitting an order.
    Integrates failure injection and randomized artificial latencies.
    """
    request_id = x_request_id or "unknown-request"
    start_time = time.time()
    
    # ------------------ DELAY INJECTION ------------------
    # Artificial random delay: 100 - 2000ms
    delay = random.uniform(0.1, 2.0)
    logger.info(
        f"Processing order transaction. Injecting intentional delay of {int(delay * 1000)}ms",
        extra={"request_id": request_id, "delay_ms": int(delay * 1000)}
    )
    await asyncio.sleep(delay)
    
    # ------------------ FAILURE INJECTION ------------------
    # 1 in 10 requests (10% rate) raises an unhandled 500 error
    if random.randint(1, 10) == 1:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "CRITICAL: Failed to write to SQL transaction log. Deadlock detected.",
            extra={"request_id": request_id, "status": 500, "duration_ms": duration_ms}
        )
        raise RuntimeError("Simulated unhandled transaction database error (Deadlock 1 in 10 rate)")

    # ------------------ CALL CHAIN EXECUTION ------------------
    async with httpx.AsyncClient() as client:
        headers = {"X-Request-ID": request_id}
        
        # Step 1: Call inventory-service for stock verification
        logger.info(
            f"Checking product stock via inventory-service: {INVENTORY_SERVICE_URL}",
            extra={"request_id": request_id}
        )
        try:
            inventory_res = await client.get(INVENTORY_SERVICE_URL, headers=headers, timeout=5.0)
            if inventory_res.status_code != 200:
                # Handle downstream error (e.g. 503 from inventory)
                duration_ms = int((time.time() - start_time) * 1000)
                logger.error(
                    f"Inventory-service failed in chain. Status: {inventory_res.status_code}",
                    extra={"request_id": request_id, "status": 500, "duration_ms": duration_ms}
                )
                return JSONResponse(
                    status_code=502,
                    content={"error": "Inventory service returned failure code", "request_id": request_id}
                )
            inventory_data = inventory_res.json()
        except httpx.RequestError as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                f"Failed connection to inventory-service: {str(exc)}",
                extra={"request_id": request_id, "status": 502, "duration_ms": duration_ms},
                exc_info=True
            )
            return JSONResponse(
                status_code=502,
                content={"error": "Inventory service unreachable", "request_id": request_id}
            )

        # Step 2: Call agent-service to trigger fraud/recommendation engine
        logger.info(
            f"Invoking AI assistant recommendation & fraud-check: {AGENT_SERVICE_URL}",
            extra={"request_id": request_id}
        )
        try:
            agent_res = await client.get(AGENT_SERVICE_URL, headers=headers, timeout=5.0)
            
            # ------------------ SCHEMA VERIFICATION ------------------
            # The agent-service might return a malformed schema occasionally.
            # We must gracefully capture it or log the schema parsing error!
            if agent_res.status_code != 200:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.warning(
                    f"Agent-service returned unsuccessful status: {agent_res.status_code}",
                    extra={"request_id": request_id, "duration_ms": duration_ms}
                )
                agent_data = {"recommendation": "default_promo", "agent_success": False, "note": "fallback mode"}
            else:
                raw_json = agent_res.json()
                # Check for schema mismatch / malformed response (1 in 10 hallucination behavior from agent)
                if not isinstance(raw_json, dict) or "decision" not in raw_json or "agent_confidence" not in raw_json:
                    duration_ms = int((time.time() - start_time) * 1000)
                    logger.error(
                        "Schema Mismatch: Agent-service returned malformed JSON structure! Enforcing fallback.",
                        extra={"request_id": request_id, "raw_response": str(raw_json), "duration_ms": duration_ms}
                    )
                    agent_data = {"error": "Malformed agent response schema", "fallback_applied": True}
                else:
                    agent_data = raw_json
        except httpx.RequestError as exc:
            logger.warning(
                f"Could not connect to agent-service: {str(exc)}. Utilizing static business rules fallback.",
                extra={"request_id": request_id},
                exc_info=True
            )
            agent_data = {"recommendation": "fallback_offline", "agent_success": False}

    duration_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "Order successfully validated and compiled.",
        extra={
            "request_id": request_id,
            "status": 200,
            "duration_ms": duration_ms
        }
    )
    
    return {
        "status": "approved",
        "inventory": inventory_data,
        "ai_analysis": agent_data,
        "duration_ms": duration_ms
    }

if __name__ == "__main__":
    print("Starting order-service on port 8002...")
    uvicorn.run("order_service:app", host="0.0.0.0", port=8002, log_level="warning")
