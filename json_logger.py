import logging
import json
from datetime import datetime

class JsonFormatter(logging.Formatter):
    """
    A custom formatter that outputs log records as structured single-line JSON.
    This format is perfect for SigNoz and OpenTelemetry collectors to parse.
    """
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Inject standard contextual fields if they are supplied in the extra dict
        standard_extras = [
            "request_id", "status", "duration_ms", "latency_ms",
            "model_name", "prompt_tokens", "completion_tokens", 
            "behavior", "service_name"
        ]
        
        for extra_field in standard_extras:
            if hasattr(record, extra_field):
                log_data[extra_field] = getattr(record, extra_field)
                
        # Capture any keys starting with 'gen_ai_' for AI observability mapping
        for key, value in record.__dict__.items():
            if key.startswith("gen_ai_"):
                log_data[key] = value

        # Include exception tracebacks if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)


def setup_logger(name: str, service_name: str) -> logging.Logger:
    """
    Initializes a logger with the custom JSON formatter and injects
    the service name into every log entry.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Avoid creating duplicate handlers if re-imported
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        
    # Injected filter to ensure service_name is always present
    class ServiceFilter(logging.Filter):
        def filter(self, record):
            record.service_name = service_name
            return True
            
    logger.addFilter(ServiceFilter())
    return logger
