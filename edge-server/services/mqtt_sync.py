import json

import paho.mqtt.client as mqtt


class CloudSyncService:
    def __init__(self, mqtt_ip: str, topic: str):
        self.mqtt_ip = mqtt_ip
        self.topic = topic
        self.cloud_sync_ok = False
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        except AttributeError:
            self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc, *args):
        # 只把“已真正连上 broker”记为在线，前端会据此显示云端/自治状态。
        self.cloud_sync_ok = (rc == 0)
        if self.cloud_sync_ok:
            print("边缘节点已成功连接至云端 MQTT")

    def _on_disconnect(self, client, userdata, rc, *args):
        self.cloud_sync_ok = False
        print("警告: 云端连接断开，进入边缘自治模式")

    def connect(self):
        try:
            # 采用 connect_async + loop_start，避免阻塞 Flask 主线程。
            self.client.connect_async(self.mqtt_ip, 1883, 60)
            self.client.loop_start()
        except Exception as exc:
            print(f"MQTT 初始化连接失败: {exc}")

    def publish(self, payload: dict):
        if not self.cloud_sync_ok:
            # 离线时静默返回 False，由边缘侧继续本地自治，不把异常扩散到主链路。
            return False
        try:
            self.client.publish(self.topic, json.dumps(payload))
            return True
        except Exception:
            return False
