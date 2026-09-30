import logging

from scale_bridge.logging_setup import configure_logging, sanitize_message


def test_sensitive_values_are_sanitized():
    message = sanitize_message(
        "password=hunter2 token:abc cookie=session database_url=postgresql://secret"
    )
    assert "hunter2" not in message
    assert "token:abc" not in message
    assert "session" not in message
    assert "postgresql://secret" not in message
    assert message.count("[REDACTED]") == 4


def test_rotating_log_is_bounded_and_contains_no_raw_sensitive_value(tmp_path):
    logger = configure_logging(tmp_path, max_bytes=120, backup_count=2)
    for number in range(30):
        logger.info("event=%s token=private-%s", number, number)
    for handler in logger.handlers:
        handler.flush()
    files = sorted(tmp_path.glob("scale-bridge.log*"))
    assert len(files) <= 3
    assert all(path.stat().st_size <= 220 for path in files)
    assert "private-" not in "".join(path.read_text(encoding="utf-8") for path in files)
    logging.getLogger("scale_bridge").handlers.clear()
