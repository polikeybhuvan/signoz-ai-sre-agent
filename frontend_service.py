import time
import uuid
import httpx
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
import uvicorn

# Import our custom JSON logger
from json_logger import setup_logger

app = FastAPI(title="Frontend Service")
logger = setup_logger("frontend_service", "frontend-service")

# Configuration
ORDER_SERVICE_URL = "http://localhost:8002/order"

@app.get("/checkout")
async def checkout(response: Response):
    """
    Simulates a client checkout request.
    Generates a unique request_id to propagate downstream and trigger the microservices call chain.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    logger.info(
        f"Received checkout request. Starting downstream order verification.",
        extra={"request_id": request_id}
    )
    
    async with httpx.AsyncClient() as client:
        try:
            # We propagate the request_id in headers to represent a distributed tracing context
            headers = {"X-Request-ID": request_id}
            
            # CALL CHAIN STEP 1: Calling the order-service
            logger.info(
                f"Calling order-service at {ORDER_SERVICE_URL}",
                extra={"request_id": request_id}
            )
            
            upstream_response = await client.get(ORDER_SERVICE_URL, headers=headers, timeout=10.0)
            duration_ms = int((time.time() - start_time) * 1000)
            
            if upstream_response.status_code == 200:
                logger.info(
                    "Checkout completed successfully.",
                    extra={
                        "request_id": request_id,
                        "status": 200,
                        "duration_ms": duration_ms
                    }
                )
                return {
                    "status": "success",
                    "request_id": request_id,
                    "duration_ms": duration_ms,
                    "order_details": upstream_response.json()
                }
            else:
                logger.error(
                    f"Order service failed with status: {upstream_response.status_code}",
                    extra={
                        "request_id": request_id,
                        "status": upstream_response.status_code,
                        "duration_ms": duration_ms
                    }
                )
                return JSONResponse(
                    status_code=502,
                    content={
                        "status": "error",
                        "message": f"Order service failed with status code {upstream_response.status_code}",
                        "request_id": request_id,
                        "duration_ms": duration_ms
                    }
                )
                
        except httpx.RequestError as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                f"Connection error occurred while calling order-service: {str(exc)}",
                extra={
                    "request_id": request_id,
                    "status": 500,
                    "duration_ms": duration_ms
                },
                exc_info=True
            )
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": "Downstream connection failure in call chain",
                    "request_id": request_id,
                    "duration_ms": duration_ms
                }
            )

if __name__ == "__main__":
    print("Starting frontend-service on port 8001...")
    uvicorn.run("frontend_service:app", host="0.0.0.0", port=8001, log_level="warning")
