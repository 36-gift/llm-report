"""
Enhanced logging configuration with structured logging support.
"""
import json
import logging
import logging.config
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from ..utils.config import config


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging."""

    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "thread_name": record.threadName,
        }

        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info) if record.exc_info else None,
            }

        # Add extra fields if requested
        if self.include_extra:
            # Add any extra fields from the log record
            extra_fields = {
                key: value
                for key, value in record.__dict__.items()
                if key
                not in {
                    "name",
                    "msg",
                    "args",
                    "levelname",
                    "levelno",
                    "pathname",
                    "filename",
                    "module",
                    "exc_info",
                    "exc_text",
                    "stack_info",
                    "lineno",
                    "funcName",
                    "created",
                    "msecs",
                    "relativeCreated",
                    "thread",
                    "threadName",
                    "processName",
                    "process",
                    "getMessage",
                }
            }
            if extra_fields:
                log_entry["extra"] = extra_fields

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class ColoredConsoleFormatter(logging.Formatter):
    """Colored console formatter for better readability."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors for console output."""
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]

        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")

        # Format the message
        formatted_message = (
            f"{color}[{timestamp}] {record.levelname:8s}{reset} "
            f"{record.name} - {record.getMessage()}"
        )

        # Add exception info if present
        if record.exc_info:
            formatted_message += f"\n{self.formatException(record.exc_info)}"

        return formatted_message


def setup_logging(
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_to_console: bool = True,
    structured_logging: bool = False,
    log_file_path: Optional[Path] = None,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> logging.Logger:
    """
    Set up comprehensive logging configuration.

    Args:
        log_level: Minimum log level to capture
        log_to_file: Whether to log to file
        log_to_console: Whether to log to console
        structured_logging: Whether to use JSON structured logging
        log_file_path: Path to log file (defaults to logs/llm_report.log)
        max_file_size: Maximum size per log file in bytes
        backup_count: Number of backup log files to keep

    Returns:
        Configured logger instance
    """
    # Clear any existing handlers
    logging.root.handlers.clear()

    # Create logs directory if logging to file
    if log_to_file:
        if log_file_path is None:
            logs_dir = config.base_dir / "logs"
            logs_dir.mkdir(exist_ok=True)
            log_file_path = logs_dir / "llm_report.log"
        else:
            log_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure logging
    handlers = []

    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        if structured_logging:
            console_handler.setFormatter(StructuredFormatter())
        else:
            console_handler.setFormatter(ColoredConsoleFormatter())
        handlers.append(console_handler)

    # File handler with rotation
    if log_to_file:
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            log_file_path, maxBytes=max_file_size, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setFormatter(StructuredFormatter())
        handlers.append(file_handler)

    # Basic configuration
    logging.basicConfig(level=getattr(logging, log_level.upper()), handlers=handlers, force=True)

    # Get the main logger
    logger = logging.getLogger("llm_report")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Set specific log levels for third-party libraries
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("webdriver_manager").setLevel(logging.WARNING)

    logger.info(
        "Logging configured",
        extra={
            "log_level": log_level,
            "log_to_file": log_to_file,
            "log_to_console": log_to_console,
            "structured_logging": structured_logging,
            "log_file_path": str(log_file_path) if log_file_path else None,
        },
    )

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def log_function_call(
    logger: logging.Logger,
    level: int = logging.DEBUG,
    include_args: bool = False,
    include_result: bool = False,
):
    """
    Decorator to log function calls.

    Args:
        logger: Logger instance to use
        level: Log level for the messages
        include_args: Whether to include function arguments in log
        include_result: Whether to include function result in log

    Returns:
        Decorator function
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            func_name = f"{func.__module__}.{func.__qualname__}"

            # Log function entry
            log_data = {"function": func_name, "event": "entry"}
            if include_args:
                log_data["args"] = args
                log_data["kwargs"] = kwargs

            logger.log(level, f"Entering function {func_name}", extra=log_data)

            try:
                result = func(*args, **kwargs)

                # Log function exit
                log_data = {"function": func_name, "event": "exit"}
                if include_result:
                    log_data["result"] = result

                logger.log(level, f"Exiting function {func_name}", extra=log_data)

                return result

            except Exception as e:
                # Log function error
                logger.log(
                    logging.ERROR,
                    f"Function {func_name} raised exception: {str(e)}",
                    extra={
                        "function": func_name,
                        "event": "error",
                        "exception_type": type(e).__name__,
                    },
                    exc_info=True,
                )
                raise

        return wrapper

    return decorator
