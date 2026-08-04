from app.core.cors_policy import (
    APPROVED_PRODUCTION_ORIGINS,
    LOCAL_DEVELOPMENT_ORIGINS,
    build_cors_origins,
    is_production_environment,
)


def test_production_aliases_exclude_local_origins():
    for environment in ("production", "prod", "live", " Production "):
        origins = build_cors_origins(
            environment=environment,
            frontend_origin="https://www.isgsuite.tr",
        )
        assert all(origin not in origins for origin in LOCAL_DEVELOPMENT_ORIGINS)
        assert is_production_environment(environment)


def test_non_production_keeps_local_development_origins():
    for environment in ("development", "staging", "test", ""):
        origins = build_cors_origins(
            environment=environment,
            frontend_origin="https://staging.example.test",
        )
        assert all(origin in origins for origin in LOCAL_DEVELOPMENT_ORIGINS)
        assert not is_production_environment(environment)


def test_configured_frontend_origin_is_preserved():
    custom_origin = "https://customer.example.test"
    origins = build_cors_origins(
        environment="production",
        frontend_origin=custom_origin,
    )
    assert origins[0] == custom_origin
    assert all(origin in origins for origin in APPROVED_PRODUCTION_ORIGINS)


def test_origins_are_trimmed_deduplicated_and_empty_values_are_ignored():
    origins = build_cors_origins(
        environment="production",
        frontend_origin="  https://www.isgsuite.tr  ",
    )
    assert origins.count("https://www.isgsuite.tr") == 1
    assert "" not in origins
