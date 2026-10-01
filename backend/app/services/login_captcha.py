"""NSL-202603: account-wide budget with a human challenge, never an account lock."""
import hashlib
import hmac
import ipaddress
from threading import BoundedSemaphore

import anyio
import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.core.rate_limit import login_account_budget

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
_verification_slots = BoundedSemaphore(8)


def login_protection_configuration() -> dict:
    return {"enabled": settings.login_captcha_enabled,
            "site_key": settings.turnstile_site_key if settings.login_captcha_enabled else ""}


def _challenge(retry: int) -> HTTPException:
    return HTTPException(429, detail={
        "code": "login_captcha_required",
        "message": "Güvenlik doğrulamasını tamamlayıp tekrar giriş yapın.",
        "site_key": settings.turnstile_site_key,
    }, headers={"Retry-After": str(max(1, min(retry or 600, 600)))})


def enforce_login_captcha(identifier: str, user_id: int | None, token: str | None, ip: str | None) -> None:
    if not settings.login_captcha_enabled:
        return
    # Email and username of the same account must spend the same budget.
    canonical = f"user:{user_id}" if user_id is not None else f"unknown:{identifier.strip().casefold()}"
    digest = hmac.new(settings.secret_key.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    allowed, retry = anyio.from_thread.run(login_account_budget, f"login-account:{digest}", settings.login_account_window_limit)
    if allowed:
        return
    if not token:
        raise _challenge(retry)
    data = {"secret": settings.turnstile_secret_key, "response": token}
    try:
        # Never forward unvalidated/spoofed header text to the CAPTCHA provider.
        data["remoteip"] = str(ipaddress.ip_address(ip or ""))
    except ValueError:
        pass
    if not _verification_slots.acquire(blocking=False):
        raise HTTPException(503, "Güvenlik doğrulaması yoğun. Lütfen kısa süre sonra tekrar deneyin.")
    try:
        try:
            response = httpx.post(SITEVERIFY_URL, data=data, timeout=5.0, follow_redirects=False)
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError):
            raise HTTPException(503, "Güvenlik doğrulaması geçici olarak kullanılamıyor. Lütfen tekrar deneyin.") from None
    finally:
        _verification_slots.release()
    hosts = {host.strip().lower() for host in settings.turnstile_allowed_hostnames.split(",") if host.strip()}
    if not isinstance(result, dict) or not (
        result.get("success") is True
        and isinstance(result.get("hostname"), str)
        and result["hostname"].lower() in hosts
        and result.get("action") == "login"
    ):
        raise _challenge(retry)
    # Siteverify rejects expired and previously consumed tokens. One accepted
    # challenge permits this request only, never clears the global budget.
