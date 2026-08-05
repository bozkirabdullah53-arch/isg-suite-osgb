from app.api.training_consistency import router


def test_static_catalog_routes_precede_dynamic_nace_route():
    paths = [route.path for route in router.routes]
    dynamic_index = paths.index("/training-consistency/catalog/{nace_code}")
    assert paths.index("/training-consistency/catalog/report") < dynamic_index
    assert paths.index("/training-consistency/catalog/materialize") < dynamic_index
    assert paths.index("/training-consistency/catalog/versions") < dynamic_index
    assert paths.index("/training-consistency/legacy-trainings/report") < dynamic_index
