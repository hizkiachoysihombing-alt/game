"""
Logging configuration for the application.
"""

import logging
import logging.config
import json
from app.core.config import settings


def setup_logging():
    """Configure logging for the application."""
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            },
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "default" if settings.APP_ENV == "development" else "json",
                "stream": "ext://sys.stdout"
            },
        },
        "root": {
            "level": settings.DEBUG and "DEBUG" or "INFO",
            "handlers": ["console"]
        }
    }
    
    logging.config.dictConfig(config)
    return logging.getLogger(__name__)


logger = logging.getLogger(__name__)
