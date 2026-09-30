import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

SENSITIVE = re.compile(
    r"(?i)(cookie|authorization|token|password|secret|database[_ -]?url|connection[_ -]?string)"
    r"\s*[:=]\s*[^\s,;]+"
)


def sanitize_message(value):
    return SENSITIVE.sub(lambda match: f"{match.group(1)}=[REDACTED]", str(value))


class SanitizingFormatter(logging.Formatter):
    def format(self, record):
        rendered = super().format(record)
        return sanitize_message(rendered)


def configure_logging(log_dir, *, max_bytes=1_048_576, backup_count=10):
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        directory / "scale-bridge.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(
        SanitizingFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logger = logging.getLogger("scale_bridge")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
