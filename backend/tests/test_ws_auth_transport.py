from app.core.deps import _ws_extract_device_password, _ws_extract_token


class FakeWebSocket:
    def __init__(
        self,
        *,
        query_params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.query_params = query_params or {}
        self.headers = headers or {}


def test_ws_jwt_comes_from_subprotocol_and_not_query_string() -> None:
    protocol_socket = FakeWebSocket(
        headers={
            "sec-websocket-protocol": "iot-jwt, header.payload.signature",
        }
    )
    query_socket = FakeWebSocket(
        query_params={"access_token": "must-not-be-read"}
    )

    assert _ws_extract_token(protocol_socket) == "header.payload.signature"
    assert _ws_extract_token(query_socket) is None


def test_ws_non_browser_client_can_still_use_authorization_header() -> None:
    websocket = FakeWebSocket(
        headers={"authorization": "Bearer header-client-token"}
    )

    assert _ws_extract_token(websocket) == "header-client-token"


def test_device_password_comes_from_header_or_subprotocol_never_query() -> None:
    protocol_socket = FakeWebSocket(
        headers={"sec-websocket-protocol": "iot-device, device-secret"}
    )
    header_socket = FakeWebSocket(
        headers={"x-device-password": "header-device-secret"}
    )
    query_socket = FakeWebSocket(
        query_params={"device_password": "must-not-be-read"}
    )

    assert _ws_extract_device_password(protocol_socket) == "device-secret"
    assert _ws_extract_device_password(header_socket) == "header-device-secret"
    assert _ws_extract_device_password(query_socket) is None
