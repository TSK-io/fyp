import paho.mqtt.client as mqtt
import pymysql
import json
import time

# --- MySQL 数据库配置 ---
DB_CONFIG = {
    'host': 'localhost',
    'user': 'saffron_user', # 填你刚才创建的用户名
    'password': 'Saffron_2026', # 填你的密码
    'database': 'saffron_db',
    'charset': 'utf8mb4'
}

# 确保 MySQL 里有这张表 (如果还没建的话)
def init_db():
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cloud_sensor_data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            device_id INT,
            temperature FLOAT,
            humidity FLOAT,
            lux FLOAT,
            soil FLOAT,
            timestamp DATETIME
        )
    """)
    conn.commit()
    conn.close()

# --- MQTT 回调函数 ---
def on_connect(client, userdata, flags, rc):
    print("成功连接到 MQTT Broker, 状态码:", rc)
    client.subscribe("saffron/telemetry") # 订阅主题

def on_message(client, userdata, msg):
    payload = msg.payload.decode('utf-8')
    print(f"收到数据: {payload}")
    try:
        data = json.loads(payload)
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        sql = """INSERT INTO cloud_sensor_data 
                 (device_id, temperature, humidity, lux, soil, timestamp) 
                 VALUES (%s, %s, %s, %s, %s, %s)"""
        val = (
            data.get('device_id', 1),
            data.get('temperature'),
            data.get('humidity'),
            data.get('lux'),
            data.get('soil'),
            data.get('timestamp')
        )
        cursor.execute(sql, val)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"数据写入 MySQL 失败: {e}")

# --- 主程序 ---
init_db()
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

print("⏳ 正在连接 MQTT 并监听数据...")
client.connect("127.0.0.1", 1883, 60)
client.loop_forever() # 保持一直运行
