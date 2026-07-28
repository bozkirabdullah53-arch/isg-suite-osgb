from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID


def ensure_demo_signing_cert(pfx_path: Path, password: str) -> tuple[object, x509.Certificate, list]:
    """Create/load a local demo PFX so the full sign flow works without a USB card."""
    if pfx_path.exists():
        return load_pfx(pfx_path, password)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "TR"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "OSGB Signer"),
            x509.NameAttribute(NameOID.COMMON_NAME, "OSGB Signer Demo Imzalayan"),
        ]
    )
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    pfx_bytes = pkcs12.serialize_key_and_certificates(
        name=b"OSGB Signer Demo",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode("utf-8")),
    )
    pfx_path.parent.mkdir(parents=True, exist_ok=True)
    pfx_path.write_bytes(pfx_bytes)
    return key, cert, []


def load_pfx(pfx_path: Path, password: str) -> tuple[object, x509.Certificate, list]:
    data = pfx_path.read_bytes()
    key, cert, additional = pkcs12.load_key_and_certificates(data, password.encode("utf-8"))
    if key is None or cert is None:
        raise ValueError("PFX içinde imza anahtarı/sertifika bulunamadı.")
    return key, cert, list(additional or [])


def ensure_localhost_tls(pfx_path: Path, password: str) -> Path:
    if pfx_path.exists():
        return pfx_path

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "OSGB Signer localhost")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1825))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(__import__("ipaddress").IPv4Address("127.0.0.1"))]
            ),
            critical=False,
        )
        .add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    pfx_bytes = pkcs12.serialize_key_and_certificates(
        name=b"localhost",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode("utf-8")),
    )
    pfx_path.parent.mkdir(parents=True, exist_ok=True)
    pfx_path.write_bytes(pfx_bytes)
    return pfx_path


def cert_info(cert: x509.Certificate, cert_id: str, source: str) -> dict:
    subject = cert.subject.rfc4514_string()
    cn = ""
    for attr in cert.subject:
        if attr.oid == NameOID.COMMON_NAME:
            cn = attr.value
            break
    return {
        "id": cert_id,
        "common_name": cn or subject,
        "subject": subject,
        "issuer": cert.issuer.rfc4514_string(),
        "serial": format(cert.serial_number, "x"),
        "not_after": cert.not_valid_after_utc.isoformat(),
        "source": source,
        "sha256": hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest(),
    }


def sign_pdf_pades(
    pdf_bytes: bytes,
    key,
    cert: x509.Certificate,
    othercerts: list,
    reason: str = "OSGB belge imzası",
    location: str = "Türkiye",
) -> bytes:
    from endesive.pdf import cms

    date = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S+00'00'")
    dct = {
        "aligned": 0,
        "sigflags": 3,
        "sigflagsft": 132,
        "sigpage": 0,
        "sigbutton": False,
        "sigfield": "Signature1",
        "auto_sigfield": True,
        "sigandcertify": True,
        "signaturebox": (40, 40, 240, 100),
        "signature": reason,
        "contact": "www.isgsuite.tr",
        "location": location,
        "signingdate": date,
        "reason": reason,
    }
    return cms.sign(pdf_bytes, dct, key, cert, othercerts, "sha256")


def sign_pdf_pkcs11(
    pdf_bytes: bytes,
    module_path: str,
    pin: str,
    reason: str = "OSGB belge imzası",
    location: str = "Türkiye",
) -> tuple[bytes, dict]:
    """PKCS#11 / PCSC e-imza kartı ile PAdES (endesive + PyKCS11). PIN lokal kalır."""
    from endesive import hsm
    from endesive.pdf import cms

    try:
        import PyKCS11
    except ImportError as exc:
        raise RuntimeError("PyKCS11 gerekli. Agent venv: pip install PyKCS11") from exc

    class _CardHsm(hsm.BaseHSM):
        def __init__(self, dll: str, user_pin: str):
            self._pin = user_pin
            self._pkcs11 = PyKCS11.PyKCS11Lib()
            self._pkcs11.load(dll)
            slots = self._pkcs11.getSlotList(tokenPresent=True)
            if not slots:
                raise RuntimeError("USB e-imza kartı bulunamadı (PCSC slot boş).")
            self._slot = slots[0]
            self._session = None
            self._key = None
            self.cert_x509 = None
            self.cert_info = None

        def certificate(self):
            self._session = self._pkcs11.openSession(
                self._slot, PyKCS11.CKF_SERIAL_SESSION | PyKCS11.CKF_RW_SESSION
            )
            self._session.login(self._pin)
            keys = self._session.findObjects(
                [(PyKCS11.CKA_CLASS, PyKCS11.CKO_PRIVATE_KEY), (PyKCS11.CKA_SIGN, PyKCS11.CK_TRUE)]
            )
            if not keys:
                raise RuntimeError("Kartta imza özel anahtarı bulunamadı.")
            self._key = keys[0]
            certs = self._session.findObjects([(PyKCS11.CKA_CLASS, PyKCS11.CKO_CERTIFICATE)])
            if not certs:
                raise RuntimeError("Kartta sertifika bulunamadı.")
            der = bytes(self._session.getAttributeValue(certs[0], [PyKCS11.CKA_VALUE])[0])
            self.cert_x509 = x509.load_der_x509_certificate(der)
            self.cert_info = cert_info(self.cert_x509, "pkcs11", "pkcs11")
            keyid = bytes(self._session.getAttributeValue(self._key, [PyKCS11.CKA_ID])[0] or b"1")
            pem = self.cert_x509.public_bytes(serialization.Encoding.PEM)
            return keyid, pem

        def sign(self, keyid, data, mech):  # noqa: ARG002
            mechanism = {
                "sha1": PyKCS11.Mechanism(PyKCS11.CKM_SHA1_RSA_PKCS, None),
                "sha256": PyKCS11.Mechanism(PyKCS11.CKM_SHA256_RSA_PKCS, None),
                "sha384": PyKCS11.Mechanism(PyKCS11.CKM_SHA384_RSA_PKCS, None),
                "sha512": PyKCS11.Mechanism(PyKCS11.CKM_SHA512_RSA_PKCS, None),
            }.get(mech, PyKCS11.Mechanism(PyKCS11.CKM_SHA256_RSA_PKCS, None))
            return bytes(bytearray(self._session.sign(self._key, data, mechanism)))

        def cleanup(self):
            try:
                if self._session is not None:
                    self._session.logout()
                    self._session.closeSession()
            except Exception:  # noqa: BLE001
                pass

    card = _CardHsm(module_path, pin)
    try:
        date = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S+00'00'")
        dct = {
            "aligned": 0,
            "sigflags": 3,
            "sigflagsft": 132,
            "sigpage": 0,
            "sigbutton": False,
            "sigfield": "Signature1",
            "auto_sigfield": True,
            "sigandcertify": True,
            "signaturebox": (40, 40, 240, 100),
            "signature": reason,
            "contact": "www.isgsuite.tr",
            "location": location,
            "signingdate": date,
            "reason": reason,
        }
        signed = cms.sign(pdf_bytes, dct, None, None, [], "sha256", card)
        info = card.cert_info or {"id": "pkcs11", "common_name": "PKCS#11", "source": "pkcs11"}
        return signed, info
    finally:
        card.cleanup()
