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
from services.agronomy_service import AgronomyService
from services.camera_service import CameraService
from services.device_service import DeviceService
from services.llm_service import LocalLLMService
from services.mqtt_sync import CloudSyncService
from services.vision_service import VisionService


def create_app():
    # 先准备运行目录和数据库中的默认记录，避免后续服务初始化时缺少依赖资源。
    ensure_runtime_dirs()
    db.create_tables()
    db_device_id = db.ensure_default_device()
    db.ensure_default_irrigation_policy(db_device_id)

    # 统一在这里装配所有长生命周期服务，便于测试和后续替换实现。
    runtime_state = RuntimeState()
    auth = AuthManager(db, SECRET_KEY, TOKEN_MAX_AGE, ADMIN_TOKEN)
    cloud_sync_service = CloudSyncService(CLOUD_MQTT_IP, MQTT_TOPIC)
    llm_service = LocalLLMService(LLM_MODEL_PATH)
    agronomy_service = AgronomyService()
    camera_service = CameraService(CAPTURES_DIR)
    vision_service = VisionService(ANALYSIS_DIR)
    device_service = DeviceService(
        db_module=db,
        runtime_state=runtime_state,
        cloud_sync_service=cloud_sync_service,
        agronomy_service=agronomy_service,
        device_id=db_device_id,
        serial_port=SERIAL_PORT,
        baud_rate=SERIAL_BAUD_RATE,
    )

    app = Flask(__name__)
    CORS(app)
    # 将依赖显式注入路由层，而不是在路由文件里直接创建对象。
    register_routes(
        app,
        auth=auth,
        runtime_state=runtime_state,
        camera_service=camera_service,
        vision_service=vision_service,
        llm_service=llm_service,
        agronomy_service=agronomy_service,
        device_service=device_service,
        require_admin_for_control=REQUIRE_ADMIN_FOR_CONTROL,
        admin_token=ADMIN_TOKEN,
        db_device_id=db_device_id,
    )

    # 通过 extensions 暴露服务对象，方便主进程启动后台任务，也方便测试访问。
    app.extensions["saffron_services"] = {
        "auth": auth,
        "runtime_state": runtime_state,
        "cloud_sync_service": cloud_sync_service,
        "llm_service": llm_service,
        "agronomy_service": agronomy_service,
        "camera_service": camera_service,
        "vision_service": vision_service,
        "device_service": device_service,
        "db_device_id": db_device_id,
    }
    return app


app = create_app()


if __name__ == "__main__":
    services = app.extensions["saffron_services"]
    # Web 服务启动前先把边缘侧依赖服务拉起。
    services["cloud_sync_service"].connect()
    try:
        services["camera_service"].start()
    except Exception as exc:
        print(f"启动摄像头失败: {exc}")
        services["camera_service"].available = False
    services["device_service"].start_background_workers()
    print("启动统一服务器... 请在浏览器中访问 http://<你的树莓派IP>:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
