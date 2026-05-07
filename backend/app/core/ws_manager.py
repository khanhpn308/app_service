from fastapi import WebSocket
import logging

# Thiết lập log để dễ dàng theo dõi trạng thái thiết bị
logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Lưu trữ kết nối theo ID thiết bị: { "ESP32_01": <WebSocket object> }
        self.active_devices: dict[str, WebSocket] = {}
        # Có thể thêm danh sách lưu các trình duyệt (dashboard) đang xem dữ liệu
        self.dashboard_clients: list[WebSocket] = []

    async def connect_device(self, device_id: str, websocket: WebSocket):
        """Chấp nhận và đăng ký thiết bị ESP32 mới"""
        await websocket.accept()
        self.active_devices[device_id] = websocket
        logger.info(f"ESP32 [{device_id}] đã kết nối. Tổng số: {len(self.active_devices)}")

    def disconnect_device(self, device_id: str):
        """Xóa thiết bị khỏi danh sách khi rớt mạng"""
        if device_id in self.active_devices:
            del self.active_devices[device_id]
            logger.info(f"ESP32 [{device_id}] rớt mạng/ngắt kết nối.")

    async def broadcast_to_dashboards(self, data: dict):
        """Đẩy dữ liệu cảm biến từ ESP32 lên tất cả các trình duyệt đang theo dõi"""
        for client in self.dashboard_clients:
            await client.send_json(data)

    async def send_command_to_device(self, device_id: str, command: dict):
        """Gửi lệnh cấu hình hoặc điều khiển rơ-le xuống đúng 1 ESP32 cụ thể"""
        websocket = self.active_devices.get(device_id)
        if websocket:
            await websocket.send_json(command)
        else:
            logger.warning(f"Không thể gửi lệnh: Thiết bị {device_id} đang offline.")

# Khởi tạo instance duy nhất (Singleton) để dùng chung trên toàn bộ dự án
manager = ConnectionManager()