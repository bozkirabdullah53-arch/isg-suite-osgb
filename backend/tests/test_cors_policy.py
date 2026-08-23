from app.core.cors_policy import build_cors_origins


def test_additive_frontend_origins_preserve_existing_origin():
    origins = build_cors_origins(
        environment="staging",
        frontend_origin="https://isg-suite-web-staging.onrender.com",
        frontend_origins=(
            "https://isg-suite-mobile-sync-canary-web-20260823.onrender.com, "
            "https://isg-suite-web-staging.onrender.com"
        ),
    )

    assert origins[:2] == [
        "https://isg-suite-web-staging.onrender.com",
        "https://isg-suite-mobile-sync-canary-web-20260823.onrender.com",
    ]
    assert "http://localhost:5173" in origins


def test_production_origin_policy_remains_without_local_origins():
    origins = build_cors_origins(
        environment="production",
        frontend_origin="https://www.isgsuite.tr",
        frontend_origins="https://canary.example",
    )

    assert "https://canary.example" in origins
    assert "http://localhost:5173" not in origins
