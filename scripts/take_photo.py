from picamera2 import Picamera2
import time

# 初始化摄像头
picam2 = Picamera2()

# 启动摄像头
picam2.start()

# 等待2秒，让摄像头进行自动对焦、曝光等调整
time.sleep(2)

# 定义照片文件名，可以包含路径
filepath = "/home/pi/Desktop/image_from_python.jpg"

# 拍照并保存文件
picam2.capture_file(filepath)
print(f"照片已保存至: {filepath}")

# 停止摄像头
picam2.stop()
