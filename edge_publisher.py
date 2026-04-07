import sqlite3
import paho.mqtt.client as mqtt
import json
import time
import os

# --- 配置 ---
CLOUD_MQTT_IP = "104.248.150.11" # 你的云服务器 IP
TOPIC = "saffron/telemetry"
# 指向你树莓派本地的 SQLite 数据库
DB_PATH = os.path.join(os.path.dirname(__file__), 'edge-server/data.sqlite3')

# 消除版本警告的写法
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)

def connect_mqtt():
    while True:
        try:
            print(f"尝试连接云端 MQTT Broker ({CLOUD_MQTT_IP})...")
            client.connect(CLOUD_MQTT_IP, 1883, 60)
            client.loop_start() 
            print("连接云端成功！")
            break
        except Exception as e:
            print(f"连接失败，5秒后重试... ({e})")
            time.sleep(5)

def sync_data():
    last_sent_id = 0
    # 找到当前数据库最大的 ID，从这里开始发
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(id) FROM sensor_data")
        res = cursor.fetchone()[0]
        if res:
            last_sent_id = res
        conn.close()
    except Exception:
        pass

    print(f"开始同步数据上云... (起始 ID: {last_sent_id})")

    while True:
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # 抓取比 last_sent_id 更新的数据
            cursor.execute("SELECT * FROM sensor_data WHERE id > ? ORDER BY id ASC LIMIT 50", (last_sent_id,))
            rows = cursor.fetchall()
            
            for row in rows:
                data = dict(row)
                payload = json.dumps(data)
                client.publish(TOPIC, payload)
                print(f"已发送: {payload}")
                last_sent_id = data['id']
                time.sleep(0.1)
            
            conn.close()
        except Exception as e:
            print(f"读取本地 SQLite 错误: {e}")
        
        # 每隔 2 秒检查一次本地数据库有没有新数据
        time.sleep(2) 

if __name__ == '__main__':
    connect_mqtt()
    sync_data()
