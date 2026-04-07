from flask import Flask
from flask_cors import CORS

import db
from auth import AuthManager
from config import (
    ADMIN_TOKEN,
    ANALYSIS_DIR,
    CAPTURES_DIR,
    CLOUD_MQTT_IP,
    LLM_MODEL_PATH,
    MQTT_TOPIC,
    REQUIRE_ADMIN_FOR_CONTROL,
    SECRET_KEY,
    SERIAL_BAUD_RATE,
    SERIAL_PORT,
    TOKEN_MAX_AGE,
    ensure_runtime_dirs,
)
from routes import register_routes
from runtime import RuntimeState
from services.camera_service import CameraService
from services.device_service import DeviceService
from services.llm_service import LocalLLMService
from services.mqtt_sync import CloudSyncService
from services.vision_service import VisionService


def create_app():
    ensure_runtime_dirs()
    db.create_tables()
    db_device_id = db.ensure_default_device()
    db.ensure_default_irrigation_policy(db_device_id)

    runtime_state = RuntimeState()
    auth = AuthManager(db, SECRET_KEY, TOKEN_MAX_AGE, ADMIN_TOKEN)
    cloud_sync_service = CloudSyncService(CLOUD_MQTT_IP, MQTT_TOPIC)
    llm_service = LocalLLMService(LLM_MODEL_PATH)
    camera_service = CameraService(CAPTURES_DIR)
    vision_service = VisionService(ANALYSIS_DIR)
    device_service = DeviceService(
        db_module=db,
        runtime_state=runtime_state,
        cloud_sync_service=cloud_sync_service,
        device_id=db_device_id,
        serial_port=SERIAL_PORT,
        baud_rate=SERIAL_BAUD_RATE,
    )

    app = Flask(__name__)
    CORS(app)
    register_routes(
        app,
        auth=auth,
        runtime_state=runtime_state,
        camera_service=camera_service,
        vision_service=vision_service,
        llm_service=llm_service,
        device_service=device_service,
        require_admin_for_control=REQUIRE_ADMIN_FOR_CONTROL,
        admin_token=ADMIN_TOKEN,
        db_device_id=db_device_id,
    )

    app.extensions["saffron_services"] = {
        "auth": auth,
        "runtime_state": runtime_state,
        "cloud_sync_service": cloud_sync_service,
        "llm_service": llm_service,
        "camera_service": camera_service,
        "vision_service": vision_service,
        "device_service": device_service,
        "db_device_id": db_device_id,
    }
    return app


app = create_app()


if __name__ == "__main__":
    services = app.extensions["saffron_services"]
    services["cloud_sync_service"].connect()
    try:
        services["camera_service"].start()
    except Exception as exc:
        print(f"启动摄像头失败: {exc}")
        services["camera_service"].available = False
    services["device_service"].start_background_workers()
    print("启动统一服务器... 请在浏览器中访问 http://<你的树莓派IP>:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
