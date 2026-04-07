import threading
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RuntimeState:
    latest_data: dict = field(default_factory=lambda: {
        "temperature": None,
        "humidity": None,
        "lux": None,
        "soil": None,
        "gesture": None,
        "timestamp": None,
    })
    auto_irrigation_state: dict = field(default_factory=lambda: {
        "watering": False,
        "last_start_ts": None,
        "last_end_ts": None,
        "last_reason": None,
        "effective_threshold": None,
        "recommended_duration": None,
        "decision_hint": "等待智能决策",
    })
    actuator_feedback: dict = field(default_factory=lambda: {
        "actuator": None,
        "action": None,
        "success": None,
        "message": "等待执行器状态更新",
        "timestamp": None,
    })
    data_lock: threading.Lock = field(default_factory=threading.Lock)
    serial_lock: threading.Lock = field(default_factory=threading.Lock)

    def update_latest_data(self, payload: dict):
        with self.data_lock:
            self.latest_data.update(payload)

    def snapshot_latest_data(self) -> dict:
        with self.data_lock:
            return self.latest_data.copy()

    def snapshot_irrigation_state(self) -> dict:
        return self.auto_irrigation_state.copy()

    def update_irrigation_decision(self, *, effective_threshold=None, recommended_duration=None,
                                   last_reason=None, decision_hint=None):
        self.auto_irrigation_state.update({
            "effective_threshold": effective_threshold,
            "recommended_duration": recommended_duration,
            "last_reason": last_reason,
            "decision_hint": decision_hint,
        })

    def update_actuator_feedback(self, *, actuator=None, action=None, success=None, message=None):
        self.actuator_feedback.update({
            "actuator": actuator,
            "action": action,
            "success": success,
            "message": message,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        })

    def snapshot_actuator_feedback(self) -> dict:
        return self.actuator_feedback.copy()
