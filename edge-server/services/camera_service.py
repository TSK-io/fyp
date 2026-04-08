from datetime import datetime
import os


try:
    from picamera2 import Picamera2

    PICAMERA_AVAILABLE = True
except Exception as exc:
    PICAMERA_AVAILABLE = False
    Picamera2 = None
    print(f"警告: picamera2 初始化失败: {exc}。拍照/视觉功能将不可用。")


class CameraService:
    def __init__(self, captures_dir: str):
        self.captures_dir = captures_dir
        self.available = False
        self.picam2 = None
        if PICAMERA_AVAILABLE:
            try:
                # 这里只先创建设备对象，真正 start 放到应用启动阶段执行。
                self.picam2 = Picamera2()
                self.available = True
                print("picamera2 库加载成功，摄像头对象已创建。")
            except Exception as exc:
                print(f"警告: picamera2 初始化失败: {exc}。拍照/视觉功能将不可用。")

    def start(self):
        if not self.available or not self.picam2:
            return
        # 项目只需要静态抓拍，所以直接使用 still configuration。
        still_config = self.picam2.create_still_configuration()
        self.picam2.configure(still_config)
        self.picam2.start()
        print("摄像头已成功启动并准备就绪。")

    def capture(self, prefix: str = "saffron") -> tuple[str, str]:
        if not self.available or not self.picam2:
            raise RuntimeError("摄像头模块不可用或未初始化。")
        # 文件名带时间戳，便于追踪一次分析对应的原始拍照时刻。
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.jpg"
        filepath = os.path.join(self.captures_dir, filename)
        self.picam2.capture_file(filepath)
        return filename, filepath
