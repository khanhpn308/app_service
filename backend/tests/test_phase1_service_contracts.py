import importlib.util


EXPECTED_SYMBOLS = {
    "app.core.webp_validator": {
        "WebPMetadata",
        "WebPValidationError",
        "validate_webp",
    },
    "app.core.map_access": {
        "is_user_active",
        "can_manage_group",
        "can_view_group",
    },
    "app.core.map_archive": {
        "DeleteReason",
        "LocationArchiveError",
        "archive_location",
    },
}


def test_phase1_service_modules_expose_the_contract() -> None:
    for module_name, symbols in EXPECTED_SYMBOLS.items():
        spec = importlib.util.find_spec(module_name)
        assert spec is not None, f"Missing module: {module_name}"

        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        assert symbols <= set(vars(module))
