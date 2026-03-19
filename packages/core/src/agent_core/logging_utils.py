import logging
import sys
from pathlib import Path


def setup_logger(log_level: str = "INFO", log_file: str | None = None) -> None:
    """Configure the root logger for the agent.

    Args:
        log_level: The logging level (e.g., "DEBUG", "INFO").
        log_file: Optional path to a file to write logs to.
    """
    logger = logging.getLogger("agent_core")

    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    # Prevent adding handlers multiple times if instantiated repeatedly
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | [%(name)s] [%(session_id)s] %(message)s"
    )

    # We use a custom filter to inject session_id if available, defaulting to "Global"
    class SessionFilter(logging.Filter):
        def filter(self, record):
            if not hasattr(record, "session_id"):
                record.session_id = getattr(record, "session_id", "Global")
            return True

    session_filter = SessionFilter()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(session_filter)
    logger.addHandler(console_handler)

    # File handler
    if log_file:
        file_path = Path(log_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(session_filter)
        logger.addHandler(file_handler)


def get_logger(name: str):
    return logging.getLogger(f"agent_core.{name}")
