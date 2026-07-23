import importlib.util


EXPECTED_SYMBOLS = {
    "app.schemas.map_groups": {
        "GroupCreate",
        "GroupPatch",
        "GroupPublic",
        "InvitationCreate",
        "InvitationPatch",
        "InvitationPublic",
        "MembershipPublic",
    },
    "app.api.map_groups_routes": {"router"},
}


def test_phase2_modules_expose_group_and_invitation_contracts() -> None:
    for module_name, symbols in EXPECTED_SYMBOLS.items():
        spec = importlib.util.find_spec(module_name)
        assert spec is not None, f"Missing module: {module_name}"

        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        assert symbols <= set(vars(module))


def test_group_router_is_mounted_in_the_application_api() -> None:
    from app.api.router import api_router

    routes = {
        (route.path, ",".join(sorted(getattr(route, "methods", None) or [])))
        for route in api_router.routes
    }
    assert ("/map-groups", "GET") in routes
    assert ("/map-groups", "POST") in routes
    assert ("/map-groups/{group_id}", "PATCH") in routes
