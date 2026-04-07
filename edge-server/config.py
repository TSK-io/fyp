import os


BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
CAPTURES_DIR = os.path.join(STATIC_DIR, "captures")
ANALYSIS_DIR = os.path.join(STATIC_DIR, "analysis")

SECRET_KEY = os.environ.get("SECRET_KEY", "saffron-secret")
TOKEN_MAX_AGE = int(os.environ.get("TOKEN_MAX_AGE", str(7 * 24 * 3600)))
REQUIRE_ADMIN_FOR_CONTROL = os.environ.get("REQUIRE_ADMIN_FOR_CONTROL", "0") in ("1", "true", "TRUE")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "saffron-admin")

CLOUD_MQTT_IP = os.environ.get("CLOUD_MQTT_IP", "104.248.150.11")
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", "saffron/telemetry")

SERIAL_PORT = os.environ.get("SERIAL_PORT", "/dev/ttyACM0")
SERIAL_BAUD_RATE = int(os.environ.get("SERIAL_BAUD_RATE", "115200"))

LLM_MODEL_PATH = os.path.join(BASE_DIR, "models", "qwen2.5-0.5b-instruct-q4_k_m.gguf")


def ensure_runtime_dirs():
    os.makedirs(CAPTURES_DIR, exist_ok=True)
    os.makedirs(ANALYSIS_DIR, exist_ok=True)
