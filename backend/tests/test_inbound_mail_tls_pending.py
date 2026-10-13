"""Provider-ready TLS regression for the deferred inbound mail rollout."""
import pytest
from unittest.mock import Mock
from app.core.config import settings


def test_pop3_requires_verified_tls_before_credentials(monkeypatch):
    from app.services import inbound_mail
    monkeypatch.setattr(settings, 'inbound_mail_use_ssl', False)
    monkeypatch.setattr(inbound_mail.time, 'sleep', lambda _: None)
    server = Mock()
    server.stls.side_effect = inbound_mail.poplib.error_proto('STLS unavailable')
    monkeypatch.setattr(inbound_mail.poplib, 'POP3', Mock(return_value=server))
    with pytest.raises(RuntimeError):
        inbound_mail._connect_pop3_with_retry()
    server.user.assert_not_called()
    server.pass_.assert_not_called()


