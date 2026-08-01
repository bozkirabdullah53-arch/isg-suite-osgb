"""Render Shell: Cloudflare R2/S3 yazma-okuma-silme doğrulaması.

Kullanım: python scripts/check_object_storage.py
Secret değerlerini veya nesne anahtarını ekrana yazmaz.
"""
from app.services.object_store import verify_object_storage_write


def main() -> int:
    result = verify_object_storage_write()
    if result.get("ok"):
        print(
            "OBJECT_STORAGE_PROBE_OK "
            f"verified_bytes={result.get('verified_bytes')} "
            f"elapsed_ms={result.get('elapsed_ms')}"
        )
        return 0
    print(
        "OBJECT_STORAGE_PROBE_FAILED "
        f"status={result.get('status')} "
        f"error={result.get('error_class', 'configuration')}"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
