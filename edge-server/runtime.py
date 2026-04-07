import threading
from dataclasses import dataclass, field


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
