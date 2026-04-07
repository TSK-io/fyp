import csv
import io

from flask import Response, jsonify, render_template, request, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import db


def register_routes(app, *, auth, runtime_state, camera_service, vision_service, llm_service, device_service,
                    require_admin_for_control, admin_token, db_device_id):
    def normalize_start_end(start_value, end_value):
        def norm_one(value, is_start):
            if not value:
                return None
            value = value.strip()
            if len(value) == 10 and value[4] == "-" and value[7] == "-":
                return value + (" 00:00:00" if is_start else " 23:59:59")
            return value

        return norm_one(start_value, True), norm_one(end_value, False)

    def parse_device_id(raw_value):
        if raw_value is None:
            return db_device_id
        return int(raw_value)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/admin")
    def admin_page():
        return render_template("admin.html")

    @app.route("/history")
    def history_page():
        return render_template("history.html")

    @app.route("/login")
    def login_page():
        return render_template("login.html")

    @app.route("/api/v1/camera/capture", methods=["POST"])
    def capture_photo():
        if not camera_service.available:
            return jsonify({"status": "error", "message": "摄像头模块不可用或未初始化。"}), 503
        try:
            filename, filepath = camera_service.capture("saffron")
            print(f"照片已保存至: {filepath}")
            return jsonify({
                "status": "success",
                "message": "照片拍摄成功！",
                "path": f"static/captures/{filename}",
            })
        except Exception as exc:
            return jsonify({"status": "error", "message": f"拍照失败: {exc}"}), 500

    @app.route("/api/v1/vision/analyze", methods=["POST"])
    def analyze_vision():
        if not camera_service.available:
            return jsonify({"status": "error", "message": "摄像头模块不可用或未初始化。"}), 503
        try:
            _, filepath = camera_service.capture("capture_for_analysis")
            analysis_result = vision_service.analyze_flower_color(filepath)
            analysis_result["analysis_image_url"] = url_for(
                "static",
                filename=f"analysis/{analysis_result.pop('analysis_filename')}",
                _external=False,
            )
            return jsonify(analysis_result)
        except Exception as exc:
            return jsonify({"status": "error", "message": f"AI分析流程出错: {exc}"}), 500

    @app.route("/api/v1/assistant", methods=["POST"])
    def ai_assistant():
        if not llm_service.available:
            return jsonify({"status": "error", "message": "LLM未配置或模型文件不存在。"}), 503
        try:
            env_data = runtime_state.snapshot_latest_data()
            payload = request.get_json() or {}
            user_msg = payload.get("message", "请简短评估当前环境是否适合藏红花生长，并给出建议。")
            answer = llm_service.answer(env_data, user_msg)
            return jsonify({"status": "success", "answer": answer})
        except Exception as exc:
            return jsonify({"status": "error", "message": str(exc)}), 500

    @app.route("/api/v1/control", methods=["POST"])
    def control_device():
        if require_admin_for_control:
            provided = request.headers.get("X-Admin-Token")
            user = auth.get_current_user()
            if not auth.is_admin_request(user=user, provided_token=provided):
                return jsonify({"error": "admin required"}), 403
        payload = request.get_json(silent=True) or {}
        command = payload.get("command")
        if not command:
            return jsonify({"status": "error", "message": "Command not provided"}), 400
        success = device_service.send_command(command)
        if success:
            return jsonify({"status": "success", "message": f"Command '{command}' sent."})
        return jsonify({"status": "error", "message": "Device not connected or busy."}), 503

    @app.route("/api/v1/auth/register", methods=["POST"])
    def register():
        payload = request.get_json(silent=True) or {}
        username = (payload.get("username") or "").strip()
        password = payload.get("password") or ""
        if not username or not password:
            return jsonify({"error": "username/password required"}), 400
        if db.get_user_by_username(username):
            return jsonify({"error": "username exists"}), 409
        uid = db.create_user(username, generate_password_hash(password))
        try:
            if db.count_users() == 1:
                db.assign_role_to_user(uid, "admin")
        except Exception:
            pass
        token = auth.issue_token(uid)
        return jsonify({
            "id": uid,
            "username": username,
            "roles": db.get_user_roles(uid),
            "token": token,
        })

    @app.route("/api/v1/auth/login", methods=["POST"])
    def login():
        payload = request.get_json(silent=True) or {}
        username = (payload.get("username") or "").strip()
        password = payload.get("password") or ""
        user = db.get_user_by_username(username)
        if not user or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "invalid credentials"}), 401
        return jsonify({
            "token": auth.issue_token(user["id"]),
            "id": user["id"],
            "username": user["username"],
            "roles": db.get_user_roles(user["id"]),
        })

    @app.route("/api/v1/auth/me", methods=["GET"])
    @auth.auth_required
    def me():
        user = request.current_user
        return jsonify({"id": user["id"], "username": user["username"], "roles": user.get("roles", [])})

    @app.route("/api/v1/sensors/latest", methods=["GET"])
    def get_latest_sensor_data():
        data = runtime_state.snapshot_latest_data()
        data["cloud_ok"] = device_service.cloud_sync_service.cloud_sync_ok
        return jsonify(data)

    @app.route("/api/v1/sensors/history", methods=["GET"])
    def get_sensor_history():
        start, end = normalize_start_end(request.args.get("start"), request.args.get("end"))
        try:
            limit = max(1, min(1000, int(request.args.get("limit", "100"))))
            offset = max(0, int(request.args.get("offset", "0")))
            device_id = parse_device_id(request.args.get("device_id"))
        except Exception:
            return jsonify({"error": "invalid limit/offset/device_id"}), 400
        rows = db.query_sensor_history(device_id=device_id, start=start, end=end, limit=limit, offset=offset)
        return jsonify({"items": rows, "count": len(rows)})

    @app.route("/api/v1/policy/irrigation", methods=["GET"])
    def get_irrigation_policy_api():
        try:
            device_id = parse_device_id(request.args.get("device_id"))
        except Exception:
            return jsonify({"error": "invalid device_id"}), 400
        return jsonify(db.get_irrigation_policy(device_id) or {})

    @app.route("/api/v1/policy/irrigation", methods=["POST"])
    def set_irrigation_policy_api():
        payload = request.get_json(silent=True) or {}
        provided = request.headers.get("X-Admin-Token") or payload.get("admin_token") or request.args.get("admin_token")
        user = auth.get_current_user()
        if not auth.is_admin_request(user=user, provided_token=provided):
            return jsonify({"error": "admin required"}), 403

        enabled = payload.get("enabled")
        if enabled in (True, False):
            enabled_int = 1 if enabled else 0
        elif isinstance(enabled, int) and enabled in (0, 1):
            enabled_int = enabled
        else:
            return jsonify({"error": "enabled must be boolean"}), 400

        try:
            soil_value = float(payload.get("soil_threshold_min")) if payload.get("soil_threshold_min") is not None else None
            duration_value = int(payload.get("watering_seconds")) if payload.get("watering_seconds") is not None else None
            cooldown_value = int(payload.get("cooldown_seconds")) if payload.get("cooldown_seconds") is not None else None
            device_id = parse_device_id(payload.get("device_id"))
        except Exception:
            return jsonify({"error": "invalid soil_threshold_min/watering_seconds/cooldown_seconds/device_id"}), 400

        db.upsert_irrigation_policy(device_id, enabled_int, soil_value, duration_value, cooldown_value)
        return jsonify(db.get_irrigation_policy(device_id) or {}), 200

    @app.route("/api/v1/policy/irrigation/status", methods=["GET"])
    def get_auto_irrigation_status():
        state = runtime_state.snapshot_irrigation_state()
        state["actuator_feedback"] = runtime_state.snapshot_actuator_feedback()
        return jsonify(state)

    @app.route("/api/v1/sensors/history.csv", methods=["GET"])
    def get_sensor_history_csv():
        start, end = normalize_start_end(request.args.get("start"), request.args.get("end"))
        try:
            limit = max(1, min(10000, int(request.args.get("limit", "1000"))))
            offset = max(0, int(request.args.get("offset", "0")))
            device_id = parse_device_id(request.args.get("device_id"))
        except Exception:
            return jsonify({"error": "invalid limit/offset/device_id"}), 400
        rows = db.query_sensor_history(device_id=device_id, start=start, end=end, limit=limit, offset=offset)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "device_id", "timestamp", "temperature", "humidity", "lux", "soil"])
        for row in rows:
            writer.writerow([row.get("id"), row.get("device_id"), row.get("timestamp"), row.get("temperature"),
                             row.get("humidity"), row.get("lux"), row.get("soil")])
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": 'attachment; filename="history.csv"'},
        )

    @app.route("/api/v1/control/logs", methods=["GET"])
    def get_control_logs():
        actuator = request.args.get("actuator")
        start, end = normalize_start_end(request.args.get("start"), request.args.get("end"))
        try:
            limit = max(1, min(1000, int(request.args.get("limit", "100"))))
            offset = max(0, int(request.args.get("offset", "0")))
            device_id = parse_device_id(request.args.get("device_id"))
        except Exception:
            return jsonify({"error": "invalid limit/offset/device_id"}), 400
        rows = db.query_control_logs_range(
            device_id=device_id,
            start=start,
            end=end,
            actuator=actuator,
            limit=limit,
            offset=offset,
        )
        return jsonify({"items": rows, "count": len(rows)})

    @app.route("/api/v1/devices/status", methods=["GET"])
    def device_status():
        try:
            device_id = parse_device_id(request.args.get("device_id"))
        except Exception:
            return jsonify({"error": "invalid device_id"}), 400
        row = db.query_device_status(device_id)
        if not row:
            return jsonify({"error": "device not found"}), 404
        return jsonify(row)
