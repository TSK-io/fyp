import json
import threading
import time
from datetime import datetime

import serial


class DeviceService:
    def __init__(self, db_module, runtime_state, cloud_sync_service, agronomy_service,
                 device_id: int, serial_port: str, baud_rate: int):
        self.db = db_module
        self.runtime_state = runtime_state
        self.cloud_sync_service = cloud_sync_service
        self.agronomy_service = agronomy_service
        self.device_id = device_id
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.serial_conn = None

    def start_background_workers(self):
        # 一个线程负责“收数”，一个线程负责“按策略执行浇水”。
        threading.Thread(target=self.serial_reader, daemon=True).start()
        threading.Thread(target=self.irrigation_worker, daemon=True).start()

    def serial_reader(self):
        while True:
            try:
                # 串口对象会被读线程和写命令逻辑共享，因此连接动作也放到锁里。
                with self.runtime_state.serial_lock:
                    self.serial_conn = serial.Serial(self.serial_port, self.baud_rate, timeout=2)
                print(f"后台线程: 成功连接到串口 {self.serial_port}")
                while True:
                    line = self.serial_conn.readline()
                    if not line:
                        continue
                    self._handle_serial_line(line)
            except serial.SerialException as exc:
                print(f"后台线程: 串口错误 - {exc}. 5秒后重试...")
                time.sleep(5)

    def _handle_serial_line(self, line: bytes):
        try:
            decoded_line = line.decode("utf-8").strip()
            if "temp" not in decoded_line:
                # STM32 可能输出调试信息；这里只消费传感器 JSON 包。
                return
            data = json.loads(decoded_line)
            ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            payload = {
                "gesture": data.get("gesture"),
                "timestamp": ts,
            }
            # 某些包可能只更新部分字段，这里保留上一次有效值，避免前端频繁闪回 "--"。
            sensor_fields = (
                ("temperature", "temp"),
                ("humidity", "humi"),
                ("lux", "lux"),
                ("soil", "soil"),
            )
            for payload_key, source_key in sensor_fields:
                value = data.get(source_key)
                if value is not None:
                    payload[payload_key] = value
            self.runtime_state.update_latest_data(payload)
            # 数据同时写入内存快照、SQLite 历史库和云端 MQTT，分别服务实时界面、历史查询和远端同步。
            self.db.insert_sensor_data(
                self.device_id,
                data.get("temp"),
                data.get("humi"),
                data.get("lux"),
                data.get("soil"),
                ts,
            )
            self.db.update_device_last_seen(self.device_id)
            cloud_payload = self.runtime_state.snapshot_latest_data()
            cloud_payload["device_id"] = self.device_id
            self.cloud_sync_service.publish(cloud_payload)
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError):
            return
        except Exception:
            return

    def send_command(self, command: str):
        success = False
        actuator = None
        action = None
        try:
            # 新版协议优先使用 JSON 指令，便于兼容更多执行器。
            parsed = json.loads(command)
            actuator = parsed.get("actuator")
            action = parsed.get("action")
        except Exception:
            # 兼容旧前端仍可能发来的简写命令。
            legacy_map = {
                "led_on": ("status_led", "on"),
                "led_off": ("status_led", "off"),
            }
            actuator, action = legacy_map.get(command, (None, None))

        with self.runtime_state.serial_lock:
            if self.serial_conn and self.serial_conn.is_open:
                try:
                    self.serial_conn.write((command + "\n").encode("utf-8"))
                    success = True
                except Exception as exc:
                    print(f"串口写入错误: {exc}")

        try:
            self.db.insert_control_log(self.device_id, actuator, action, command, success)
            if success:
                self.db.update_device_last_seen(self.device_id)
        except Exception:
            pass
        message = (
            f"执行器 {actuator or 'unknown'} 已切换为 {action or 'unknown'}"
            if success else
            f"执行器 {actuator or 'unknown'} 指令发送失败"
        )
        self.runtime_state.update_actuator_feedback(
            actuator=actuator,
            action=action,
            success=success,
            message=message,
        )
        return success

    def irrigation_worker(self):
        poll_interval = 5
        while True:
            try:
                policy = self.db.get_irrigation_policy(self.device_id)
                if not policy or not policy.get("enabled"):
                    self.runtime_state.update_irrigation_decision(
                        effective_threshold=None,
                        recommended_duration=None,
                        decision_hint="自动灌溉策略已关闭",
                    )
                    time.sleep(poll_interval)
                    continue

                duration = policy.get("watering_seconds")
                cooldown = policy.get("cooldown_seconds") or 0
                if duration is None or duration <= 0:
                    self.runtime_state.update_irrigation_decision(
                        effective_threshold=policy.get("soil_threshold_min"),
                        recommended_duration=duration,
                        decision_hint="浇水时长未配置，暂不执行自动浇水",
                    )
                    time.sleep(poll_interval)
                    continue

                cooldown = int(cooldown)
                if self._in_cooldown(cooldown):
                    self.runtime_state.update_irrigation_decision(
                        effective_threshold=self.runtime_state.auto_irrigation_state.get("effective_threshold"),
                        recommended_duration=self.runtime_state.auto_irrigation_state.get("recommended_duration"),
                        decision_hint="处于冷却期，暂缓再次浇水",
                    )
                    time.sleep(poll_interval)
                    continue

                latest_data = self.runtime_state.snapshot_latest_data()
                history_rows = self.db.query_sensor_history(device_id=self.device_id, limit=24)
                irrigation_state = self.runtime_state.snapshot_irrigation_state()
                # 灌溉决策不仅看当前土壤值，也会结合历史趋势和冷却状态。
                decision = self.agronomy_service.plan_irrigation(
                    current_data=latest_data,
                    history_rows=history_rows,
                    policy=policy,
                    irrigation_state=irrigation_state,
                )
                self.runtime_state.update_irrigation_decision(
                    effective_threshold=decision.get("effective_threshold"),
                    recommended_duration=decision.get("recommended_duration"),
                    last_reason=decision.get("reason"),
                    decision_hint=decision.get("reason"),
                )
                if decision.get("allowed") and decision.get("should_water") and not irrigation_state["watering"]:
                    self._run_irrigation_cycle(int(decision.get("recommended_duration") or duration), decision.get("reason"))
                time.sleep(poll_interval)
            except Exception:
                time.sleep(poll_interval)

    def _in_cooldown(self, cooldown: int) -> bool:
        last_end_ts = self.runtime_state.auto_irrigation_state.get("last_end_ts")
        if cooldown <= 0 or not last_end_ts:
            return False
        try:
            last_end = datetime.strptime(last_end_ts, "%Y-%m-%d %H:%M:%S")
            return (datetime.utcnow() - last_end).total_seconds() < cooldown
        except Exception:
            return False

    def _run_irrigation_cycle(self, duration: int, reason: str | None = None):
        irrigation_state = self.runtime_state.auto_irrigation_state
        command_on = json.dumps({"actuator": "pump", "action": "on"})
        success_on = self.send_command(command_on)
        if not success_on:
            return

        # 这里直接更新共享状态，让前端能立刻感知“浇水中”，不用等下一轮轮询计算。
        irrigation_state["watering"] = True
        irrigation_state["last_start_ts"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        irrigation_state["last_reason"] = reason
        irrigation_state["recommended_duration"] = duration
        irrigation_state["decision_hint"] = reason
        time.sleep(duration)

        command_off = json.dumps({"actuator": "pump", "action": "off"})
        success_off = self.send_command(command_off)
        if success_off:
            irrigation_state["last_end_ts"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        irrigation_state["watering"] = False
