"""IMAP gelen kutusu senkronizasyonu.

Bu servis yalnızca açıkça etkinleştirildiğinde çalışır. Mesajlar IMAP UID ile
idempotent biçimde alınır; uzak sunucudaki mesajlar okunmuş olarak işaretlenmez
ve hiçbir mesaj silinmez.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.parser import BytesParser
from email.policy import default
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser
import imaplib
import logging
import hashlib
import poplib
import re
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import EmailInboxMessage

logger = logging.getLogger(__name__)

_MAX_BODY_CHARS = 200_000


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data and data.strip():
            self.parts.append(data)


def inbound_mail_configured() -> bool:
    return bool(
        getattr(settings, "inbound_mail_enabled", False)
        and (settings.inbound_mail_host or "").strip()
        and (settings.inbound_mail_username or "").strip()
        and (settings.inbound_mail_password or "")
    )


def inbound_mail_status() -> dict[str, object]:
    protocol = (settings.inbound_mail_protocol or "imap").strip().lower()
    return {
        "enabled": bool(getattr(settings, "inbound_mail_enabled", False)),
        "configured": inbound_mail_configured(),
        "host": (settings.inbound_mail_host or "").strip() or None,
        "port": int(settings.inbound_mail_port),
        "folder": (settings.inbound_mail_folder or "INBOX").strip() or "INBOX",
        "protocol": protocol,
    }


def _decode_value(value: str | None, *, limit: int = 500) -> str:
    if not value:
        return ""
    try:
        decoded = str(make_header(decode_header(value)))
    except (LookupError, UnicodeDecodeError, ValueError):
        decoded = value
    return decoded.strip()[:limit]


def _decode_payload(part) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        raw = part.get_payload()
        return str(raw) if isinstance(raw, str) else ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, UnicodeError):
        return payload.decode("utf-8", errors="replace")


def _html_to_text(value: str) -> str:
    parser = _VisibleTextParser()
    try:
        parser.feed(value)
        parser.close()
        value = " ".join(parser.parts)
    except Exception:  # noqa: BLE001 — bozuk HTML gelen kutusunu durdurmasın
        value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _body_and_attachments(message) -> tuple[str, int]:
    plain: list[str] = []
    html: list[str] = []
    attachment_count = 0
    parts = message.walk() if message.is_multipart() else [message]
    for part in parts:
        if part.is_multipart():
            continue
        disposition = (part.get_content_disposition() or "").casefold()
        if disposition == "attachment":
            attachment_count += 1
            continue
        content_type = (part.get_content_type() or "").casefold()
        if content_type == "text/plain":
            plain.append(_decode_payload(part))
        elif content_type == "text/html":
            html.append(_decode_payload(part))
    body = "\n\n".join(item.strip() for item in plain if item.strip())
    if not body:
        body = _html_to_text("\n".join(html))
    return body[:_MAX_BODY_CHARS], attachment_count


def _received_at(message) -> datetime | None:
    value = message.get("date")
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except (TypeError, ValueError, OverflowError):
        return None


def _message_payload(raw: bytes, *, uid: int, mailbox: str) -> dict[str, object]:
    message = BytesParser(policy=default).parsebytes(raw)
    sender_name, sender_email = getaddresses([message.get("from", "")])[0] if message.get("from") else ("", "")
    recipient_pairs = getaddresses(message.get_all("to", []) + message.get_all("cc", []))
    recipients = ", ".join(
        address if not name else f"{name} <{address}>"
        for name, address in recipient_pairs
        if address
    )[:2000]
    body_text, attachment_count = _body_and_attachments(message)
    return {
        "mailbox": mailbox,
        "imap_uid": uid,
        "message_id": _decode_value(message.get("message-id"), limit=500) or None,
        "sender_email": (sender_email or "").strip()[:255] or None,
        "sender_name": _decode_value(sender_name, limit=160) or None,
        "recipients": recipients or None,
        "subject": _decode_value(message.get("subject"), limit=500),
        "body_text": body_text,
        "has_attachments": attachment_count > 0,
        "attachment_count": attachment_count,
        "received_at": _received_at(message),
    }


def _connect_imap_with_retry():
    """Connect and authenticate despite transient MailEnable EOF responses."""
    last_error: Exception | None = None
    for attempt in range(3):
        client = None
        try:
            if settings.inbound_mail_use_ssl:
                client = imaplib.IMAP4_SSL(
                    settings.inbound_mail_host,
                    int(settings.inbound_mail_port),
                    timeout=int(settings.inbound_mail_timeout_sec),
                )
            else:
                client = imaplib.IMAP4(
                    settings.inbound_mail_host,
                    int(settings.inbound_mail_port),
                    timeout=int(settings.inbound_mail_timeout_sec),
                )
                client.starttls()
            client.login(settings.inbound_mail_username, settings.inbound_mail_password)
            return client
        except (OSError, EOFError, imaplib.IMAP4.error) as exc:
            last_error = exc
            if client is not None:
                try:
                    client.logout()
                except Exception:  # noqa: BLE001 — retry cleanup
                    pass
            if attempt < 2:
                time.sleep(0.75 * (attempt + 1))
    raise RuntimeError("IMAP sunucusuna bağlanılamadı.") from last_error


def _connect_pop3_with_retry():
    """Connect and authenticate to POP3 after transient MailEnable failures."""
    last_error: Exception | None = None
    for attempt in range(3):
        client = None
        try:
            if settings.inbound_mail_use_ssl:
                client = poplib.POP3_SSL(settings.inbound_mail_host, int(settings.inbound_mail_port), timeout=int(settings.inbound_mail_timeout_sec))
            else:
                client = poplib.POP3(settings.inbound_mail_host, int(settings.inbound_mail_port), timeout=int(settings.inbound_mail_timeout_sec))
            client.user(settings.inbound_mail_username)
            client.pass_(settings.inbound_mail_password)
            return client
        except (OSError, EOFError, poplib.error_proto) as exc:
            last_error = exc
            if client is not None:
                try:
                    client.quit()
                except Exception:  # noqa: BLE001
                    pass
            if attempt < 2:
                time.sleep(0.75 * (attempt + 1))
    raise RuntimeError("POP3 sunucusuna bağlanılamadı.") from last_error


def _pop3_uid_number(uidl: bytes) -> int:
    return int(hashlib.sha256(uidl).hexdigest()[:7], 16)


def _sync_pop3_inbox(db: Session, result: dict[str, object], mailbox: str) -> dict[str, object]:
    client = None
    try:
        client = _connect_pop3_with_retry()
        _, uidl_rows, _ = client.uidl()
        limit = max(1, min(int(settings.inbound_mail_sync_limit or 50), 100))
        entries = []
        for row in uidl_rows[-limit:]:
            number_raw, uidl = row.split(maxsplit=1)
            entries.append((int(number_raw), _pop3_uid_number(uidl)))
        result["checked_count"] = len(entries)
        result["connected"] = True
        for number, uid in reversed(entries):
            existing = db.scalar(select(EmailInboxMessage).where(EmailInboxMessage.mailbox == mailbox, EmailInboxMessage.imap_uid == uid))
            if existing is not None:
                if existing.deleted_at is None:
                    existing.synced_at = datetime.utcnow()
                continue
            _, lines, _ = client.retr(number)
            raw = b"\n".join(lines)
            if raw:
                db.add(EmailInboxMessage(**_message_payload(raw, uid=uid, mailbox=mailbox)))
                result["new_count"] = int(result["new_count"]) + 1
        db.commit()
        return result
    finally:
        if client is not None:
            try:
                client.quit()
            except (OSError, poplib.error_proto):
                pass


def sync_inbox(db: Session) -> dict[str, object]:
    """Fetch recent INBOX messages and persist only messages not seen before."""
    status = inbound_mail_status()
    result: dict[str, object] = {
        **status,
        "connected": False,
        "new_count": 0,
        "checked_count": 0,
        "error": None,
    }
    if not inbound_mail_configured():
        result["error"] = "Gelen kutusu bağlantısı henüz yapılandırılmamış."
        return result

    mailbox = (settings.inbound_mail_folder or "INBOX").strip() or "INBOX"
    if (settings.inbound_mail_protocol or "imap").strip().lower() == "pop3":
        try:
            return _sync_pop3_inbox(db, result, mailbox)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            result["error"] = f"{type(exc).__name__}: {str(exc)[:220]}"
            logger.warning("POP3 gelen kutusu senkronizasyonu başarısız: %s", exc)
            return result
    client = None
    try:
        client = _connect_imap_with_retry()
        code, _ = client.select(mailbox, readonly=True)
        if code != "OK":
            raise RuntimeError("Gelen kutusu açılamadı.")
        code, data = client.uid("search", None, "ALL")
        if code != "OK":
            raise RuntimeError("Gelen kutusu mesajları listelenemedi.")
        raw_uids = data[0].split() if data and data[0] else []
        limit = max(1, min(int(settings.inbound_mail_sync_limit or 50), 100))
        uids = [int(value) for value in raw_uids[-limit:]]
        result["checked_count"] = len(uids)
        result["connected"] = True

        for uid in uids:
            existing = db.scalar(
                select(EmailInboxMessage).where(
                    EmailInboxMessage.mailbox == mailbox,
                    EmailInboxMessage.imap_uid == uid,
                )
            )
            if existing is not None:
                if existing.deleted_at is None:
                    existing.synced_at = datetime.utcnow()
                continue
            code, fetched = client.uid("fetch", str(uid), "(BODY.PEEK[])")
            if code != "OK":
                logger.warning("IMAP mesajı alınamadı (uid=%s)", uid)
                continue
            raw = next(
                (part[1] for part in fetched if isinstance(part, tuple) and len(part) > 1 and isinstance(part[1], bytes)),
                None,
            )
            if not raw:
                continue
            db.add(EmailInboxMessage(**_message_payload(raw, uid=uid, mailbox=mailbox)))
            result["new_count"] = int(result["new_count"]) + 1
        db.commit()
    except Exception as exc:  # noqa: BLE001 — gelen kutusu API'yi düşürmemeli
        db.rollback()
        result["error"] = f"{type(exc).__name__}: {str(exc)[:220]}"
        logger.warning("IMAP gelen kutusu senkronizasyonu başarısız: %s", exc)
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass
            try:
                client.logout()
            except Exception:  # noqa: BLE001
                pass
    return result
