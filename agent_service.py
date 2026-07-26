import asyncio
import random
import time
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
import uvicorn

# Import our custom JSON logger
from json_logger import setup_logger

app = FastAPI(title="AI Agent Service")
logger = setup_logger("agent_service", "agent-service")

@app.get("/assist")
async def assist(x_request_id: str = Header(default=None)):
    """
    Simulates a server-side LLM call using an agent wrapper.
    Models natural LLM latency profiles, token metrics, and random failure behaviors.
    """
    request_id = x_request_id or "unknown-request"
    start_time = time.time()
    
    # ------------------ DEFINE BEHAVIOR PATHS ------------------
    # Choose between:
    # 1. 'hallucination' (10% chance)
    # 2. 'slow_reasoning' (25% chance of complex reasoning / retry delay)
    # 3. 'normal' (default, standard agent behavior)
    
    rand_val = random.random()
    if random.randint(1, 10) == 1:
        behavior = "hallucination"
    elif rand_val < 0.25:
        behavior = "slow_reasoning"
    else:
        behavior = "normal"
        
    # Generate realistic model attributes
    model_name = "gpt-4o-mini"
    prompt_tokens = random.randint(50, 300)
    
    # ------------------ CALCULATE LATENCY & TOKENS ------------------
    if behavior == "normal":
        # Standard latency (300ms - 1500ms)
        llm_delay = random.uniform(0.3, 1.5)
        completion_tokens = random.randint(20, 100)
        decision = "approve"
        confidence = round(random.uniform(0.85, 0.99), 3)
        comment = "Agent verified user transaction matches safe purchasing fingerprint."
        
    elif behavior == "slow_reasoning":
        # Extra delay for deep thought/multi-turn search (1500ms - 4000ms)
        llm_delay = random.uniform(1.5, 4.0)
        # Deep reasoning uses substantially more prompt and completion tokens
        prompt_tokens += random.randint(150, 400)
        completion_tokens = random.randint(150, 350)
        decision = "approve"
        confidence = round(random.uniform(0.90, 0.98), 3)
        comment = "<thought>Checking user purchase velocity... checking historical flags... reasoning confirms safe pattern.</thought> Transaction approved."
        
    else:  # hallucination / schema mismatch
        # Simulating model spitting out random malformed schemas / garbage data
        llm_delay = random.uniform(0.5, 2.0)
        completion_tokens = random.randint(10, 50)
        
    # Apply the artificial sleep
    logger.info(
        f"Initiating agentic inference block. Behavior: '{behavior}'. Delay: {int(llm_delay * 1000)}ms",
        extra={"request_id": request_id, "behavior": behavior, "target_delay_ms": int(llm_delay * 1000)}
    )
    await asyncio.sleep(llm_delay)
    
    # Calculate exact duration
    latency_ms = int((time.time() - start_time) * 1000)
    total_tokens = prompt_tokens + completion_tokens
    
    # ------------------ OTEL SEMANTIC LOGGING ------------------
    # We structure the extra arguments so they perfectly map onto GenAI OpenTelemetry Semantic Conventions:
    # gen_ai.system, gen_ai.request.model, gen_ai.response.model, gen_ai.usage.prompt_tokens, gen_ai.usage.completion_tokens
    logger.info(
        f"Agent LLM generation completed. Model: {model_name}. Tokens: {total_tokens} (P: {prompt_tokens}, C: {completion_tokens}). Latency: {latency_ms}ms.",
        extra={
            "request_id": request_id,
            "behavior": behavior,
            "model_name": model_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_ms": latency_ms,
            "gen_ai_system": "openai",
            "gen_ai_request_model": model_name,
            "gen_ai_response_model": model_name,
            "gen_ai_usage_prompt_tokens": prompt_tokens,
            "gen_ai_usage_completion_tokens": completion_tokens,
            "gen_ai_usage_total_tokens": total_tokens
        }
    )
    
    # ------------------ SCHEMA MISMATCH RETURN ------------------
    if behavior == "hallucination":
        # Simulates a severe schema breakdown or raw string corrupting JSON layout
        # order-service is expecting: "decision" and "agent_confidence" keys.
        # Here we return a structure completely devoid of expected keys to force an upstream parsing failure.
        return {
            "status": "fatal",
            "agent_hallucinated": True,
            "gibberish_payload": "Error string: failed to match JSON schema format because model thought it was writing raw text.",
            "prompt_tokens_consumed": prompt_tokens,
            "completion_tokens_consumed": completion_tokens
        }
        
    # Normal response format
    return {
        "decision": decision,
        "agent_confidence": confidence,
        "agent_comment": comment,
        "model": model_name,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "latency_ms": latency_ms
    }

if __name__ == "__main__":
    print("Starting agent-service on port 8004...")
    uvicorn.run("agent_service:app", host="0.0.0.0", port=8004, log_level="warning")
