import logging
import os
import structlog
from structlog.stdlib import LoggerFactory


def configure_logging() -> None:
    app_env = os.getenv("APP_ENV", "development")
    is_dev = app_env.lower() == "development"
    
    # Processors for all environments
    processors = [
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if is_dev:
        # Human-readable console logs for development
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        # JSON logs for production/logging systems
        processors.append(structlog.processors.JSONRenderer())

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "app"):
    return structlog.get_logger(name)
