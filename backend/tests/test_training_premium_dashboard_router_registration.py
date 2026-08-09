from app.main import app


def test_premium_dashboard_route_is_registered():
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/api/v1/trainings/premium-dashboard" in paths
