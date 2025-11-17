import logging
import sys
import structlog
from structlog.types import Processor

from config import settings


def setup_logging(log_level: str = "INFO") -> None:
    level = getattr(logging, log_level.upper())

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    for logger_name in ["uvicorn.access", "fastapi"]:
        logging.getLogger(logger_name).handlers = []
        logging.getLogger(logger_name).propagate = False

    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.JSON_LOGS:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logger = structlog.get_logger()
    logger.info(
        "Logging configured successfully",
        log_level=log_level,
    )
