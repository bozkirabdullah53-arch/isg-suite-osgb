"""Formal authority-integration gate for İBYS and İSBS/e-Reçete.

This module is intentionally independent from the legacy generic integration
stubs.  It exists to make one rule impossible to misunderstand in code:

* A URL/API key or an HTTP 2xx response is NOT official approval.
* Real authority traffic is blocked until the authority-issued profile/test
  credentials are present and an explicit send switch is enabled.
* Secret values are never returned by readiness/status helpers.

The Ministry-specific wire protocol is deliberately NOT guessed here.  It must
be implemented only against the current official test guide supplied during the
registration process.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

AuthorityKind = Literal["ibys", "isbs_erecete"]
Mode = Literal["test", "production"]


class AuthorityGateError(RuntimeError):
    """Raised when code attempts an authority action before formal readiness."""


@dataclass(frozen=True)
class AuthorityProfile:
    authority: AuthorityKind
    mode: Mode
    endpoint_present: bool
    authority_profile_present: bool
    access_code_present: bool
    registration_present: bool
    explicit_send_enabled: bool

    @property
    def ready(self) -> bool:
        common = self.endpoint_present and self.authority_profile_present and self.access_code_present
        if self.mode == "test":
            return common and self.explicit_send_enabled
        return common and self.registration_present and self.explicit_send_enabled

    def public_snapshot(self) -> dict[str, object]:
        """Return presence flags only; no URL, token, code or secret is exposed."""
        return {
            "authority": self.authority,
            "mode": self.mode,
            "endpoint_present": self.endpoint_present,
            "authority_profile_present": self.authority_profile_present,
            "access_code_present": self.access_code_present,
            "registration_present": self.registration_present,
            "explicit_send_enabled": self.explicit_send_enabled,
            "ready": self.ready,
        }


def _present(name: str) -> bool:
    return bool((os.getenv(name) or "").strip())


def _enabled(name: str) -> bool:
    return (os.getenv(name) or "").strip().casefold() in {"1", "true", "yes", "on"}


def _ibys(mode: Mode) -> AuthorityProfile:
    if mode == "test":
        return AuthorityProfile(
            authority="ibys",
            mode=mode,
            endpoint_present=_present("IBYS_OFFICIAL_TEST_ENDPOINT"),
            authority_profile_present=_present("IBYS_OFFICIAL_PROFILE_VERSION"),
            access_code_present=_present("IBYS_OFFICIAL_TEST_CODE"),
            registration_present=_present("IBYS_OFFICIAL_REGISTRATION_NO"),
            explicit_send_enabled=_enabled("IBYS_OFFICIAL_TEST_SEND_ENABLED"),
        )
    return AuthorityProfile(
        authority="ibys",
        mode=mode,
        endpoint_present=_present("IBYS_OFFICIAL_PROD_ENDPOINT"),
        authority_profile_present=_present("IBYS_OFFICIAL_PROFILE_VERSION"),
        access_code_present=_present("IBYS_OFFICIAL_ACCESS_CODE"),
        registration_present=_present("IBYS_OFFICIAL_REGISTRATION_NO"),
        explicit_send_enabled=_enabled("IBYS_OFFICIAL_PROD_SEND_ENABLED"),
    )


def _isbs(mode: Mode) -> AuthorityProfile:
    if mode == "test":
        return AuthorityProfile(
            authority="isbs_erecete",
            mode=mode,
            endpoint_present=_present("ISBS_ERECETE_OFFICIAL_TEST_ENDPOINT"),
            authority_profile_present=_present("ISBS_ERECETE_PROFILE_VERSION"),
            access_code_present=_present("ISBS_KTS_SOFTWARE_ACCESS_TEST_CODE"),
            registration_present=_present("ISBS_KTS_REGISTRATION_NO"),
            explicit_send_enabled=_enabled("ISBS_ERECETE_TEST_SEND_ENABLED"),
        )
    return AuthorityProfile(
        authority="isbs_erecete",
        mode=mode,
        endpoint_present=_present("ISBS_ERECETE_OFFICIAL_PROD_ENDPOINT"),
        authority_profile_present=_present("ISBS_ERECETE_PROFILE_VERSION"),
        access_code_present=_present("ISBS_KTS_SOFTWARE_ACCESS_CODE"),
        registration_present=_present("ISBS_KTS_REGISTRATION_NO"),
        explicit_send_enabled=_enabled("ISBS_ERECETE_PROD_SEND_ENABLED"),
    )


def authority_profile(authority: AuthorityKind, mode: Mode = "test") -> AuthorityProfile:
    if authority == "ibys":
        return _ibys(mode)
    if authority == "isbs_erecete":
        return _isbs(mode)
    raise ValueError(f"Unsupported authority: {authority}")


def assert_authority_send_allowed(authority: AuthorityKind, mode: Mode = "test") -> AuthorityProfile:
    """Fail closed unless the complete formal profile AND explicit switch exist."""
    profile = authority_profile(authority, mode)
    if not profile.ready:
        missing = [
            key
            for key, ok in (
                ("official endpoint", profile.endpoint_present),
                ("authority profile/version", profile.authority_profile_present),
                ("authority-issued access/test code", profile.access_code_present),
                ("registration/approval number", profile.registration_present if mode == "production" else True),
                ("explicit send enable", profile.explicit_send_enabled),
            )
            if not ok
        ]
        raise AuthorityGateError(
            f"{authority} {mode} send is blocked; missing: {', '.join(missing)}. "
            "Do not bypass this gate. Obtain the current authority test/profile package first."
        )
    return profile


def public_authority_status() -> dict[str, object]:
    return {
        "ibys": {
            "test": authority_profile("ibys", "test").public_snapshot(),
            "production": authority_profile("ibys", "production").public_snapshot(),
        },
        "isbs_erecete": {
            "test": authority_profile("isbs_erecete", "test").public_snapshot(),
            "production": authority_profile("isbs_erecete", "production").public_snapshot(),
        },
        "secrets_exposed": False,
        "policy": "fail_closed_until_authority_profile_and_explicit_enable",
    }
