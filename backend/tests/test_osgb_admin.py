from app.services.osgb_admin import generate_temporary_password


def test_generate_temporary_password():
    pwd = generate_temporary_password()
    assert len(pwd) >= 12
    assert any(c.islower() for c in pwd)
    assert any(c.isupper() for c in pwd)
    assert any(c.isdigit() for c in pwd)
