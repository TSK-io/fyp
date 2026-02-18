# 传感器驱动基类
# 定义所有传感器驱动的统一接口和通用功能

import time

class SensorError(Exception):
    """传感器操作异常类"""
    def __init__(self, message, sensor_type=None, error_code=None):
        self.sensor_type = sensor_type
        self.error_code = error_code
        super().__init__(message)

class SensorBase:
    """
    传感器驱动基类
    
    所有传感器驱动都应该继承此类，实现统一的接口。
    提供通用的错误处理、状态管理等功能。
    """
    
    def __init__(self, pin, sensor_type="Unknown"):
        """
        初始化传感器
        
        参数:
            pin: MicroPython Pin对象
            sensor_type: 传感器类型字符串
        """
        self.pin = pin
        self.sensor_type = sensor_type
        self.last_read_time = 0
        self.last_error = None
        self.read_count = 0
        self.error_count = 0
        
        # 状态标志
        self.is_initialized = False
        self.is_available = False
        
        print(f"初始化{sensor_type}传感器，引脚: {pin}")
    
    def measure(self):
        """
        读取传感器数据 - 子类必须实现
        
        返回:
            bool: 读取是否成功
        """
        raise NotImplementedError("子类必须实现measure()方法")
    
    def get_data(self):
        """
        获取传感器数据 - 子类必须实现
        
        返回:
            dict: 传感器数据字典
        """
        raise NotImplementedError("子类必须实现get_data()方法")
    
    def is_ready(self):
        """
        检查传感器是否就绪
        
        返回:
            bool: 传感器是否就绪
        """
        return self.is_initialized and self.is_available
    
    def get_status(self):
        """
        获取传感器状态信息
        
        返回:
            dict: 包含状态、统计信息等
        """
        if self.read_count > 0:
            success_rate = (self.read_count - self.error_count) / self.read_count * 100
        else:
            success_rate = 0
            
        return {
            'sensor_type': self.sensor_type,
            'pin': str(self.pin),
            'is_initialized': self.is_initialized,
            'is_available': self.is_available,
            'is_ready': self.is_ready(),
            'read_count': self.read_count,
            'error_count': self.error_count,
            'success_rate': f"{success_rate:.1f}%",
            'last_read_time': self.last_read_time,
            'last_error': str(self.last_error) if self.last_error else None
        }
    
    def reset_statistics(self):
        """重置统计信息"""
        self.read_count = 0
        self.error_count = 0
        self.last_error = None
        print(f"{self.sensor_type}传感器统计信息已重置")
    
    def _update_read_stats(self, success=True, error=None):
        """
        更新读取统计信息
        
        参数:
            success: 是否读取成功
            error: 错误信息（如果有）
        """
        self.read_count += 1
        self.last_read_time = time.ticks_ms()
        
        if not success:
            self.error_count += 1
            self.last_error = error
    
    def _log_info(self, message):
        """记录信息日志"""
        print(f"[{self.sensor_type}] {message}")
    
    def _log_error(self, message):
        """记录错误日志"""
        print(f"[{self.sensor_type}] ❌ {message}")
    
    def _log_success(self, message):
        """记录成功日志"""
        print(f"[{self.sensor_type}] ✅ {message}")
    
    def __str__(self):
        """字符串表示"""
        return f"{self.sensor_type}(pin={self.pin}, ready={self.is_ready()})"
    
    def __repr__(self):
        """详细字符串表示"""
        status = self.get_status()
        return f"{self.sensor_type}(pin={self.pin}, success_rate={status['success_rate']})"
