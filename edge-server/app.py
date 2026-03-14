# Saffron_Edge_Server/app.py (优化版 v4.0 - 集成边云协同 MQTT)

import serial
import json
import threading
import time
import io, csv
from datetime import datetime
from flask import Flask, jsonify, render_template, request, Response, url_for
from flask_cors import CORS
import os
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash
import cv2
import numpy as np

# --- 新增: MQTT 云端同步配置 ---
import paho.mqtt.client as mqtt

CLOUD_MQTT_IP = "104.248.150.11"
MQTT_TOPIC = "saffron/telemetry"
cloud_sync_ok = False

# 兼容不同版本的 paho-mqtt
try:
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
except AttributeError:
    mqtt_client = mqtt.Client()

def on_mqtt_connect(client, userdata, flags, rc, *args):
    global cloud_sync_ok
    if rc == 0:
        cloud_sync_ok = True
        print("✅ 边缘节点已成功连接至云端 MQTT")
    else:
        cloud_sync_ok = False

def on_mqtt_disconnect(client, userdata, rc, *args):
    global cloud_sync_ok
    cloud_sync_ok = False
    print("⚠ 云端连接断开，进入边缘自治模式")

mqtt_client.on_connect = on_mqtt_connect
mqtt_client.on_disconnect = on_mqtt_disconnect

try:
    # 异步连接，绝不阻塞本地边缘计算服务
    mqtt_client.connect_async(CLOUD_MQTT_IP, 1883, 60)
    mqtt_client.loop_start()
except Exception as e:
    print(f"MQTT 初始化连接失败: {e}")
# ---------------------------

try:
    from llama_cpp import Llama
    LLM_AVAILABLE = True
    print("✅ llama_cpp 库加载成功。")
except Exception as e:
    LLM_AVAILABLE = False
    print(f"⚠️ 警告: llama_cpp 初始化失败: {e}。本地 LLM 功能将不可用。")

llm_model = None
LLM_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'models', 'qwen2.5-0.5b-instruct-q4_k_m.gguf')

def get_llm():
    global llm_model
    if llm_model is None and LLM_AVAILABLE and os.path.exists(LLM_MODEL_PATH):
        print("🤖 正在加载 Qwen 模型到内存，请稍候...")
        llm_model = Llama(
            model_path=LLM_MODEL_PATH, 
            n_ctx=512, 
            n_threads=4, 
            verbose=False
        )
        print("✅ Qwen 模型加载完成！")
    return llm_model

PI_CAMERA_AVAILABLE = False
picam2 = None
try:
    from picamera2 import Picamera2
    picam2 = Picamera2()
    PI_CAMERA_AVAILABLE = True
    print("✅ picamera2 库加载成功，摄像头对象已创建。")
except Exception as e:
    print(f"⚠️ 警告: picamera2 初始化失败: {e}。拍照/视觉功能将不可用。")

try:
    from . import db as db
except Exception:
    import db

data_lock = threading.Lock()
latest_data = { "temperature": None, "humidity": None, "lux": None, "soil": None, "gesture": None, "timestamp": None }
db.create_tables()
DB_DEVICE_ID = db.ensure_default_device()
serial_lock = threading.Lock()
SECRET_KEY = os.environ.get('SECRET_KEY', 'saffron-secret')
TOKEN_MAX_AGE = int(os.environ.get('TOKEN_MAX_AGE', str(7*24*3600)))
serializer = URLSafeTimedSerializer(SECRET_KEY, salt='auth-token')
REQUIRE_ADMIN_FOR_CONTROL = os.environ.get('REQUIRE_ADMIN_FOR_CONTROL', '0') in ('1','true','TRUE')
ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN', 'saffron-admin')
ser = None
auto_irrigation_state = { "watering": False, "last_start_ts": None, "last_end_ts": None }

CAPTURES_DIR = os.path.join(os.path.dirname(__file__), 'static', 'captures')
if not os.path.exists(CAPTURES_DIR):
    os.makedirs(CAPTURES_DIR)
ANALYSIS_DIR = os.path.join(os.path.dirname(__file__), 'static', 'analysis')
if not os.path.exists(ANALYSIS_DIR):
    os.makedirs(ANALYSIS_DIR)

def _get_bearer_token():
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '): return auth[len('Bearer '):].strip()
    return None
def issue_token(user_id: int) -> str: return serializer.dumps({'uid': int(user_id)})
def verify_token(token: str):
    try:
        data = serializer.loads(token, max_age=TOKEN_MAX_AGE)
        return int(data.get('uid'))
    except (BadSignature, SignatureExpired, Exception): return None
def get_current_user():
    token = _get_bearer_token()
    if not token: return None
    uid = verify_token(token)
    if not uid: return None
    user = db.get_user_by_id(uid)
    if not user: return None
    user['roles'] = db.get_user_roles(uid)
    return user
def auth_required(fn):
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user: return jsonify({"error": "unauthorized"}), 401
        request.current_user = user
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper
def admin_required(fn):
    def wrapper(*args, **kwargs):
        provided = request.headers.get('X-Admin-Token')
        if provided == ADMIN_TOKEN: return fn(*args, **kwargs)
        user = get_current_user()
        if not user or ('admin' not in (user.get('roles') or [])): return jsonify({"error": "admin required"}), 403
        request.current_user = user
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper

def serial_reader():
    global latest_data, ser
    serial_port = '/dev/ttyACM0'
    baud_rate = 115200
    while True:
        try:
            with serial_lock:
                ser = serial.Serial(serial_port, baud_rate, timeout=2)
            print(f"后台线程: 成功连接到串口 {serial_port}")
            while True:
                line = ser.readline()
                if line:
                    try:
                        decoded_line = line.decode('utf-8').strip()
                        if 'temp' in decoded_line:
                            data = json.loads(decoded_line)
                            ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                            with data_lock:
                                latest_data['temperature'] = data.get('temp')
                                latest_data['humidity'] = data.get('humi')
                                latest_data['lux'] = data.get('lux')
                                latest_data['soil'] = data.get('soil')
                                latest_data['gesture'] = data.get('gesture')
                                latest_data['timestamp'] = ts
                                
                                # 存入本地数据库
                                try:
                                    db.insert_sensor_data(DB_DEVICE_ID, data.get('temp'), data.get('humi'), data.get('lux'), data.get('soil'), ts)
                                    db.update_device_last_seen(DB_DEVICE_ID)
                                    
                                    # --- 新增: 实时触发云端同步 ---
                                    if cloud_sync_ok:
                                        payload = latest_data.copy()
                                        payload['device_id'] = DB_DEVICE_ID
                                        try:
                                            mqtt_client.publish(MQTT_TOPIC, json.dumps(payload))
                                        except Exception:
                                            pass
                                    # ------------------------------
                                except Exception: pass
                    except (UnicodeDecodeError, json.JSONDecodeError, KeyError): pass
        except serial.SerialException as e:
            print(f"后台线程: 串口错误 - {e}. 5秒后重试...")
            time.sleep(5)

def irrigation_worker():
    global ser
    POLL_INTERVAL = 5
    while True:
        try:
            policy = db.get_irrigation_policy(DB_DEVICE_ID)
            if not policy or not policy.get('enabled'):
                time.sleep(POLL_INTERVAL); continue
            threshold = policy.get('soil_threshold_min')
            duration = policy.get('watering_seconds')
            cooldown = policy.get('cooldown_seconds') or 0
            if threshold is None or duration is None or duration <= 0:
                time.sleep(POLL_INTERVAL); continue
            try: cd = int(cooldown)
            except Exception: cd = 0
            if cd > 0 and auto_irrigation_state.get("last_end_ts"):
                try:
                    last_end = datetime.strptime(auto_irrigation_state["last_end_ts"], '%Y-%m-%d %H:%M:%S')
                    if (datetime.utcnow() - last_end).total_seconds() < cd:
                        time.sleep(POLL_INTERVAL); continue
                except Exception: pass
            with data_lock: soil = latest_data.get('soil')
            if soil is None:
                time.sleep(POLL_INTERVAL); continue
            if soil < threshold and not auto_irrigation_state["watering"]:
                cmd_on = json.dumps({"actuator": "pump", "action": "on"})
                success_on = False
                with serial_lock:
                    if ser and ser.is_open:
                        try:
                            ser.write((cmd_on + "\n").encode('utf-8')); success_on = True
                        except Exception: success_on = False
                try: db.insert_control_log(DB_DEVICE_ID, "pump", "on", cmd_on, success_on)
                except Exception: pass
                if success_on:
                    auto_irrigation_state["watering"] = True
                    auto_irrigation_state["last_start_ts"] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    time.sleep(int(duration))
                    cmd_off = json.dumps({"actuator": "pump", "action": "off"})
                    success_off = False
                    with serial_lock:
                        if ser and ser.is_open:
                            try:
                                ser.write((cmd_off + "\n").encode('utf-8')); success_off = True
                            except Exception: success_off = False
                    try: db.insert_control_log(DB_DEVICE_ID, "pump", "off", cmd_off, success_off)
                    except Exception: pass
                    if success_off: auto_irrigation_state["last_end_ts"] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    auto_irrigation_state["watering"] = False
            time.sleep(POLL_INTERVAL)
        except Exception: time.sleep(POLL_INTERVAL)


app = Flask(__name__)
CORS(app)

def analyze_flower_color(image_path):
    try:
        image = cv2.imread(image_path)
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        color_ranges = {
            'red': ([0, 120, 70], [10, 255, 255]),
            'green': ([35, 80, 40], [85, 255, 255]),
            'pink': ([140, 100, 100], [170, 255, 255])
        }
        scores = {}
        for color, (lower, upper) in color_ranges.items():
            lower_bound = np.array(lower)
            upper_bound = np.array(upper)
            mask = cv2.inRange(hsv_image, lower_bound, upper_bound)
            scores[color] = cv2.countNonZero(mask)

        if not any(scores.values()):
            detected_color = 'none'
        else:
            detected_color = max(scores, key=scores.get)
            
        if detected_color != 'none':
            lower, upper = color_ranges[detected_color]
            mask = cv2.inRange(hsv_image, np.array(lower), np.array(upper))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest_contour = max(contours, key=cv2.contourArea)
                if cv2.contourArea(largest_contour) > 500:
                    x, y, w, h = cv2.boundingRect(largest_contour)
                    cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    text_y = y - 10 if y - 10 > 10 else y + 20
                    cv2.putText(image, f"{detected_color}", (x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        growth_stage_map = {
            'green': '花蕾期 (Budding Stage)',
            'pink': '盛开期 (Flowering Stage)',
            'red': '成熟/凋谢期 (Mature/Withered Stage)',
            'none': '未识别到有效目标'
        }
        growth_stage = growth_stage_map.get(detected_color, '未知')

        cv2.putText(image, f"Color: {detected_color}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(image, f"Stage: {growth_stage}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        analysis_filename = 'analyzed_' + os.path.basename(image_path)
        analysis_filepath = os.path.join(ANALYSIS_DIR, analysis_filename)
        cv2.imwrite(analysis_filepath, image)
        
        return {
            "status": "success",
            "detected_color": detected_color,
            "growth_stage": growth_stage,
            "scores": scores,
            "analysis_image_url": url_for('static', filename=f'analysis/{analysis_filename}', _external=False)
        }
    except Exception as e:
        print(f"❌ 视觉分析失败: {e}")
        return {"status": "error", "message": str(e)}

@app.route('/')
def index(): return render_template('index.html')
@app.route('/admin')
def admin_page(): return render_template('admin.html')
@app.route('/history')
def history_page(): return render_template('history.html')
@app.route('/login')
def login_page(): return render_template('login.html')

@app.route('/api/v1/camera/capture', methods=['POST'])
def capture_photo():
    if not PI_CAMERA_AVAILABLE or not picam2:
        return jsonify({"status": "error", "message": "摄像头模块不可用或未初始化。"}), 503
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"saffron_{timestamp}.jpg"
        filepath = os.path.join(CAPTURES_DIR, filename)
        picam2.capture_file(filepath)
        print(f"照片已保存至: {filepath}")
        relative_path = os.path.join('static', 'captures', filename)
        return jsonify({
            "status": "success", 
            "message": f"照片拍摄成功！",
            "path": relative_path
        })
    except Exception as e:
        return jsonify({"status": "error", "message": f"拍照失败: {e}"}), 500

@app.route('/api/v1/vision/analyze', methods=['POST'])
def analyze_vision():
    if not PI_CAMERA_AVAILABLE or not picam2:
        return jsonify({"status": "error", "message": "摄像头模块不可用或未初始化。"}), 503
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"capture_for_analysis_{timestamp}.jpg"
        filepath = os.path.join(CAPTURES_DIR, filename)
        picam2.capture_file(filepath)
        analysis_result = analyze_flower_color(filepath)
        return jsonify(analysis_result)
    except Exception as e:
        return jsonify({"status": "error", "message": f"AI分析流程出错: {e}"}), 500

@app.route('/api/v1/assistant', methods=['POST'])
def ai_assistant():
    if not LLM_AVAILABLE or not os.path.exists(LLM_MODEL_PATH):
        return jsonify({"status": "error", "message": "LLM未配置或模型文件不存在。"}), 503
    try:
        with data_lock: env_data = latest_data.copy()
        temp = env_data.get('temperature', '未知')
        humi = env_data.get('humidity', '未知')
        lux = env_data.get('lux', '未知')
        soil = env_data.get('soil', '未知')
        data = request.get_json() or {}
        user_msg = data.get('message', '请简短评估当前环境是否适合藏红花生长，并给出建议。')

        prompt = (
            f"<|im_start|>system\n"
            f"你是一个专业的藏红花种植AI助手。请根据以下当前环境数据回答问题，要求语言简明扼要，控制在100字以内。\n"
            f"当前温度:{temp}℃, 湿度:{humi}%, 光照:{lux}lux, 土壤湿度:{soil}%。<|im_end|>\n"
            f"<|im_start|>user\n{user_msg}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        model = get_llm()
        if not model: return jsonify({"status": "error", "message": "模型加载失败。"}), 500

        response = model(prompt, max_tokens=150, stop=["<|im_end|>"], echo=False)
        answer = response['choices'][0]['text'].strip()
        return jsonify({"status": "success", "answer": answer})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/v1/control', methods=['POST'])
def control_device():
    if REQUIRE_ADMIN_FOR_CONTROL:
        provided = request.headers.get('X-Admin-Token')
        user = get_current_user()
        roles = (user.get('roles') if user else []) or []
        if not (provided == ADMIN_TOKEN or ('admin' in roles)): return jsonify({"error":"admin required"}), 403
    data = request.get_json()
    command = data.get('command')
    if not command: return jsonify({"status": "error", "message": "Command not provided"}), 400
    success = False
    actuator = None
    action = None
    try:
        parsed = json.loads(command)
        actuator = parsed.get('actuator')
        action = parsed.get('action')
    except Exception: pass
    with serial_lock:
        if ser and ser.is_open:
            try:
                ser.write((command + '\n').encode('utf-8'))
                success = True
            except Exception as e: print(f"串口写入错误: {e}")
    try:
        db.insert_control_log(DB_DEVICE_ID, actuator, action, command, success)
        if success: db.update_device_last_seen(DB_DEVICE_ID)
    except Exception: pass
    if success: return jsonify({"status": "success", "message": f"Command '{command}' sent."})
    else: return jsonify({"status": "error", "message": "Device not connected or busy."}), 503

@app.route('/api/v1/auth/register', methods=['POST'])
def register():
    payload = request.get_json(silent=True) or {}
    username = (payload.get('username') or '').strip()
    password = payload.get('password') or ''
    if not username or not password: return jsonify({"error":"username/password required"}), 400
    if db.get_user_by_username(username): return jsonify({"error":"username exists"}), 409
    pwd_hash = generate_password_hash(password)
    uid = db.create_user(username, pwd_hash)
    try:
        if db.count_users() == 1: db.assign_role_to_user(uid, 'admin')
    except Exception: pass
    token = issue_token(uid)
    return jsonify({"id": uid, "username": username, "roles": db.get_user_roles(uid), "token": token})

@app.route('/api/v1/auth/login', methods=['POST'])
def login():
    payload = request.get_json(silent=True) or {}
    username = (payload.get('username') or '').strip()
    password = payload.get('password') or ''
    user = db.get_user_by_username(username)
    if not user or not check_password_hash(user['password_hash'], password): return jsonify({"error":"invalid credentials"}), 401
    token = issue_token(user['id'])
    return jsonify({"token": token, "id": user['id'], "username": user['username'], "roles": db.get_user_roles(user['id'])})

@app.route('/api/v1/auth/me', methods=['GET'])
@auth_required
def me():
    u = request.current_user
    return jsonify({"id": u['id'], "username": u['username'], "roles": u.get('roles', [])})

@app.route('/api/v1/sensors/latest', methods=['GET'])
def get_latest_sensor_data():
    with data_lock: data_to_return = latest_data.copy()
    # --- 注入云端连接状态给 UI ---
    data_to_return['cloud_ok'] = cloud_sync_ok
    return jsonify(data_to_return)

@app.route('/api/v1/sensors/history', methods=['GET'])
def get_sensor_history():
    def normalize_start_end(s: str | None, e: str | None):
        def norm_one(x: str | None, is_start: bool):
            if not x: return None
            x = x.strip()
            if len(x) == 10 and x[4] == '-' and x[7] == '-': return x + (' 00:00:00' if is_start else ' 23:59:59')
            return x
        return norm_one(s, True), norm_one(e, False)
    start, end = normalize_start_end(request.args.get('start'), request.args.get('end'))
    try:
        limit = max(1, min(1000, int(request.args.get('limit', '100'))))
        offset = max(0, int(request.args.get('offset', '0')))
    except Exception: return jsonify({"error": "invalid limit/offset"}), 400
    try: device_id = int(request.args.get('device_id')) if request.args.get('device_id') is not None else DB_DEVICE_ID
    except Exception: return jsonify({"error": "invalid device_id"}), 400
    rows = db.query_sensor_history(device_id=device_id, start=start, end=end, limit=limit, offset=offset)
    return jsonify({"items": rows, "count": len(rows)})

@app.route('/api/v1/policy/irrigation', methods=['GET'])
def get_irrigation_policy_api():
    try: device_id = int(request.args.get('device_id')) if request.args.get('device_id') is not None else DB_DEVICE_ID
    except Exception: return jsonify({"error": "invalid device_id"}), 400
    row = db.get_irrigation_policy(device_id)
    return jsonify(row or {})

@app.route('/api/v1/policy/irrigation', methods=['POST'])
def set_irrigation_policy_api():
    payload = request.get_json(silent=True) or {}
    provided = request.headers.get('X-Admin-Token') or payload.get('admin_token') or request.args.get('admin_token')
    is_admin = False
    user = get_current_user()
    if user and ('admin' in (user.get('roles') or [])): is_admin = True
    elif provided == ADMIN_TOKEN: is_admin = True
    if not is_admin: return jsonify({"error": "admin required"}), 403
    enabled = payload.get('enabled')
    if enabled in (True, False): enabled_int = 1 if enabled else 0
    elif isinstance(enabled, int) and enabled in (0, 1): enabled_int = enabled
    else: return jsonify({"error": "enabled must be boolean"}), 400
    try:
        soil_v = float(payload.get('soil_threshold_min')) if payload.get('soil_threshold_min') is not None else None
        dur_v = int(payload.get('watering_seconds')) if payload.get('watering_seconds') is not None else None
        cd_v = int(payload.get('cooldown_seconds')) if payload.get('cooldown_seconds') is not None else None
    except Exception: return jsonify({"error": "invalid soil_threshold_min/watering_seconds/cooldown_seconds"}), 400
    try: device_id = int(payload.get('device_id')) if payload.get('device_id') is not None else DB_DEVICE_ID
    except Exception: return jsonify({"error": "invalid device_id"}), 400
    db.upsert_irrigation_policy(device_id, enabled_int, soil_v, dur_v, cd_v)
    row = db.get_irrigation_policy(device_id)
    return jsonify(row or {}), 200

@app.route('/api/v1/policy/irrigation/status', methods=['GET'])
def get_auto_irrigation_status(): return jsonify(auto_irrigation_state)

@app.route('/api/v1/sensors/history.csv', methods=['GET'])
def get_sensor_history_csv():
    def normalize_start_end(s: str | None, e: str | None):
        def norm_one(x: str | None, is_start: bool):
            if not x: return None
            x = x.strip()
            if len(x) == 10 and x[4] == '-' and x[7] == '-': return x + (' 00:00:00' if is_start else ' 23:59:59')
            return x
        return norm_one(s, True), norm_one(e, False)
    start, end = normalize_start_end(request.args.get('start'), request.args.get('end'))
    try:
        limit = max(1, min(10000, int(request.args.get('limit', '1000'))))
        offset = max(0, int(request.args.get('offset', '0')))
    except Exception: return jsonify({"error": "invalid limit/offset"}), 400
    try: device_id = int(request.args.get('device_id')) if request.args.get('device_id') is not None else DB_DEVICE_ID
    except Exception: return jsonify({"error": "invalid device_id"}), 400
    rows = db.query_sensor_history(device_id=device_id, start=start, end=end, limit=limit, offset=offset)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['id','device_id','timestamp','temperature','humidity','lux','soil'])
    for r in rows: writer.writerow([r.get('id'), r.get('device_id'), r.get('timestamp'), r.get('temperature'), r.get('humidity'), r.get('lux'), r.get('soil')])
    csv_data = output.getvalue()
    return Response(csv_data, mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename="history.csv"'})

@app.route('/api/v1/control/logs', methods=['GET'])
def get_control_logs():
    try:
        limit = max(1, min(1000, int(request.args.get('limit', '100'))))
        offset = max(0, int(request.args.get('offset', '0')))
    except Exception: return jsonify({"error": "invalid limit/offset"}), 400
    try: device_id = int(request.args.get('device_id')) if request.args.get('device_id') is not None else DB_DEVICE_ID
    except Exception: return jsonify({"error": "invalid device_id"}), 400
    actuator = request.args.get('actuator')
    def norm(ts, is_start):
        if not ts: return None
        ts = ts.strip()
        if len(ts) == 10 and ts[4] == '-' and ts[7] == '-': return ts + (' 00:00:00' if is_start else ' 23:59:59')
        return ts
    start = norm(request.args.get('start'), True)
    end = norm(request.args.get('end'), False)
    rows = db.query_control_logs_range(device_id=device_id, start=start, end=end, actuator=actuator, limit=limit, offset=offset)
    return jsonify({"items": rows, "count": len(rows)})

@app.route('/api/v1/devices/status', methods=['GET'])
def device_status():
    try: device_id = int(request.args.get('device_id')) if request.args.get('device_id') is not None else DB_DEVICE_ID
    except Exception: return jsonify({"error": "invalid device_id"}), 400
    row = db.query_device_status(device_id)
    if not row: return jsonify({"error": "device not found"}), 404
    return jsonify(row)

if __name__ == '__main__':
    if PI_CAMERA_AVAILABLE and picam2:
        try:
            still_config = picam2.create_still_configuration()
            picam2.configure(still_config)
            picam2.start()
            print("✅ 摄像头已成功启动并准备就绪。")
        except Exception as e:
            print(f"❌ 启动摄像头失败: {e}")
            PI_CAMERA_AVAILABLE = False
    
    reader_thread = threading.Thread(target=serial_reader, daemon=True)
    reader_thread.start()

    irrigation_thread = threading.Thread(target=irrigation_worker, daemon=True)
    irrigation_thread.start()

    print("启动统一服务器... 请在浏览器中访问 http://<你的树莓派IP>:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
