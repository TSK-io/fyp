from flask import Flask, render_template, jsonify, send_file
import pymysql
import datetime
import qrcode
import io

app = Flask(__name__)

# --- MySQL 连接配置 ---
DB_CONFIG = {
    'host': 'localhost',
    'user': 'saffron_user',
    'password': 'Saffron_2026', 
    'database': 'saffron_db',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/latest')
def get_latest():
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cloud_sensor_data ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            if isinstance(row['timestamp'], datetime.datetime):
                row['timestamp'] = row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            return jsonify(row)
        return jsonify({"error": "暂无数据"})
    except Exception as e:
        return jsonify({"error": str(e)})

# --- 新增：动态生成二维码的接口 ---
@app.route('/qrcode')
def generate_qr():
    url = "http://104.248.150.11"
    # 配置二维码的细节
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="white")
    
    # 将图片存入内存并直接返回给浏览器
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
