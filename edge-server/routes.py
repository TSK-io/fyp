import csv
import io

from flask import Response, jsonify, render_template, request, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import db


def register_routes(app, *, auth, runtime_state, camera_service, vision_service, llm_service, device_service,
                    agronomy_service, require_admin_for_control, admin_token, db_device_id):
    # 统一处理日期筛选参数:
    # 前端若只传 YYYY-MM-DD，这里自动补齐为整天范围，避免查询结果不完整。
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

    # 将“实时状态 + 历史数据 + 灌溉策略”组合成一次完整诊断，供首页和 AI 助手复用。
    def build_diagnosis(device_id: int):
        current_data = runtime_state.snapshot_latest_data()
        history_rows = db.query_sensor_history(device_id=device_id, limit=36)
        policy = db.get_irrigation_policy(device_id) or {}
        irrigation_state = runtime_state.snapshot_irrigation_state()
        return agronomy_service.build_diagnosis(
            current_data=current_data,
            history_rows=history_rows,
            policy=policy,
            irrigation_state=irrigation_state,
        )

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
            # 拍照接口只负责落盘并返回静态资源路径，展示逻辑由前端处理。
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
            # 视觉分析固定走“先抓拍，再分析”的链路，保证分析对象始终是最新画面。
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
        try:
            env_data = runtime_state.snapshot_latest_data()
            payload = request.get_json() or {}
            user_msg = payload.get("message", "请简短评估当前环境是否适合藏红花生长，并给出建议。")
            # 先生成规则诊断，再把结果作为上下文传给本地 LLM，减少纯生成式回答的漂移。
            diagnosis = build_diagnosis(db_device_id)
            response = llm_service.respond(env_data, user_msg, diagnosis=diagnosis)
            return jsonify({
                "status": "success",
                "answer": response["answer"],
                "mode": response["mode"],
                "diagnosis_summary": diagnosis["summary"],
            })
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
        # 路由层只做鉴权和协议校验，真正的串口写入与日志记录交给 DeviceService。
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

    @app.route("/api/v1/intelligence/diagnosis", methods=["GET"])
    def get_intelligence_diagnosis():
        try:
            device_id = parse_device_id(request.args.get("device_id"))
        except Exception:
            return jsonify({"error": "invalid device_id"}), 400
        diagnosis = build_diagnosis(device_id)
        return jsonify({"status": "success", **diagnosis})

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
        # 兼容 header、body、query 三种 token 传入方式，方便页面和脚本复用接口。
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
        # 导出接口保持最朴素的 CSV 结构，便于直接导入 Excel 或科研分析脚本。
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
