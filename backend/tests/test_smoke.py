from app.core.security import get_password_hash, verify_password


def test_password_hash_roundtrip():
    hashed = get_password_hash("SecurePassword123!")
    assert verify_password("SecurePassword123!", hashed)
    assert not verify_password("WrongPassword", hashed)
