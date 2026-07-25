"""request_id log filter smoke."""
import logging

from app.core.request_id import RequestIdLogFilter, install_request_id_logging, request_id_ctx


def test_request_id_log_filter_sets_attribute():
    token = request_id_ctx.set("abc123")
    try:
        record = logging.LogRecord(
            name="t", level=logging.INFO, pathname=__file__, lineno=1,
            msg="hello", args=(), exc_info=None,
        )
        assert RequestIdLogFilter().filter(record) is True
        assert record.request_id == "abc123"  # type: ignore[attr-defined]
    finally:
        request_id_ctx.reset(token)


def test_install_request_id_logging_idempotent():
    install_request_id_logging()
    install_request_id_logging()
    root = logging.getLogger()
    assert any(getattr(f, "name", "") == "isg_request_id_filter" for f in root.filters)
