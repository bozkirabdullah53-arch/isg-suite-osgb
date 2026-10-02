"""Read-only provider gate: verified TLS login, no message operations or secrets.

Run from backend with its existing secure environment:
    PYTHONPATH=. python scripts/check_inbound_mail_tls.py

Does not change endpoints/settings or send, fetch, mark or delete any mail.
"""
import json
import ssl

from app.services import inbound_mail


def check_inbound_mail_tls() -> dict:
    protocol = (inbound_mail.settings.inbound_mail_protocol or "imap").strip().lower()
    result = {"ok": False, "protocol": protocol, "authenticated": False,
              "certificate_verified": False, "tls_version": None, "error_kind": None}
    if protocol not in {"imap", "pop3"}:
        result["error_kind"] = "unsupported_protocol"
        return result
    if not inbound_mail.inbound_mail_configured():
        result["error_kind"] = "not_configured"
        return result
    client = None
    try:
        client = (inbound_mail._connect_imap_with_retry() if protocol == "imap"
                  else inbound_mail._connect_pop3_with_retry())
        sock = client.sock
        if not isinstance(sock, ssl.SSLSocket) or not (
            sock.context.check_hostname and sock.context.verify_mode == ssl.CERT_REQUIRED
            and sock.getpeercert() and sock.version() in {"TLSv1.2", "TLSv1.3"}
        ):
            result["error_kind"] = "unverified_transport"
            return result
        result.update(ok=True, authenticated=True, certificate_verified=True,
                      tls_version=sock.version())
        return result
    except Exception as exc:
        # Provider errors may include mailbox addresses or configuration values;
        # report only the underlying exception class, never its message/traceback.
        cause = exc.__cause__ if exc.__cause__ is not None else exc
        result["error_kind"] = type(cause).__name__
        return result
    finally:
        if client is not None:
            inbound_mail._close_mail_client(client, protocol)


def main() -> int:
    result = check_inbound_mail_tls()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
