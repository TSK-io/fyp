# DHT11/DHT22 温湿度传感器驱动模块
# 适配 /lib 扁平化结构

import time
import sys
# 变更点：移除点号，改为直接导入
from sensor_base import SensorBase, SensorError

class DHT11Sensor(SensorBase):
    """
    DHT11/DHT22 温湿度传感器智能驱动
    """
    
    def __init__(self, pin, sensor_type='DHT11'):
        super().__init__(pin, sensor_type)
        self.temperature = None
        self.humidity = None
        self.driver_mode = None
        self.driver_instance = None
        self._initialize_driver()
    
    def _initialize_driver(self):
        # 尝试硬件级驱动
        if self._try_hardware_driver(): return
        # 尝试软件级驱动  
        if self._try_software_driver(): return
        # 使用模拟驱动
        self._use_simulated_driver()
    
    def _try_hardware_driver(self):
        try:
            import machine
            if not hasattr(machine, 'dht_readinto'): return False
            self.driver_instance = HardwareDHTDriver(self.pin, self.sensor_type)
            self.driver_mode = "hardware"
            if self.driver_instance.test_read():
                self._log_success(f"硬件级{self.sensor_type}驱动初始化成功")
                self.is_initialized = True; self.is_available = True
                return True
            else: raise Exception("硬件级驱动测试失败")
        except Exception as e:
            return False
    
    def _try_software_driver(self):
        try:
            self.driver_instance = SoftwareDHTDriver(self.pin, self.sensor_type)
            self.driver_mode = "software"
            if self.driver_instance.test_read():
                self._log_success(f"软件级{self.sensor_type}驱动初始化成功")
                self.is_initialized = True; self.is_available = True
                return True
            else: raise Exception("软件级驱动测试失败")
        except Exception as e:
            return False
    
    def _use_simulated_driver(self):
        self._log_info("启用模拟数据模式...")
        self.driver_instance = SimulatedDHTDriver(self.pin, self.sensor_type)
        self.driver_mode = "simulated"
        self.is_initialized = True; self.is_available = True
    
    def measure(self):
        if not self.is_ready(): raise SensorError("传感器未就绪", self.sensor_type, "NOT_READY")
        try:
            success = self.driver_instance.measure()
            if success:
                self.temperature = self.driver_instance.get_temperature()
                self.humidity = self.driver_instance.get_humidity()
                self._update_read_stats(True)
                return True
            else: raise Exception("驱动返回读取失败")
        except Exception as e:
            self._update_read_stats(False, e)
            if self.driver_mode != "simulated" and self.error_count >= 5:
                self._try_driver_fallback()
            return False
    
    def _try_driver_fallback(self):
        if self.driver_mode == "hardware":
            if self._try_software_driver(): return
        self._use_simulated_driver()
    
    def get_data(self):
        return {
            'temperature': self.temperature,
            'humidity': self.humidity,
            'driver_mode': self.driver_mode,
            'sensor_type': self.sensor_type,
            'timestamp': time.ticks_ms(),
            'is_valid': self.temperature is not None and self.humidity is not None
        }

# 具体驱动实现类

class HardwareDHTDriver:
    def __init__(self, pin, sensor_type):
        self.pin = pin; self.sensor_type = sensor_type; self.buf = bytearray(5)
        import machine; self.dht_readinto = machine.dht_readinto
        time.sleep_ms(1000)
    
    def measure(self):
        try:
            self.pin.init(self.pin.IN, self.pin.PULL_UP)
            self.dht_readinto(self.pin, self.buf)
            checksum = (self.buf[0] + self.buf[1] + self.buf[2] + self.buf[3]) & 0xFF
            if checksum != self.buf[4]: raise Exception("CheckSum Err")
            return True
        except Exception: return False
    
    def get_temperature(self):
        if self.sensor_type == 'DHT22':
            t = ((self.buf[2] & 0x7F) << 8 | self.buf[3]) * 0.1
            if self.buf[2] & 0x80: t = -t
            return t
        else: return self.buf[2]
    
    def get_humidity(self):
        if self.sensor_type == 'DHT22': return (self.buf[0] << 8 | self.buf[1]) * 0.1
        else: return self.buf[0]
    
    def test_read(self):
        try: return self.measure()
        except: return False

class SoftwareDHTDriver:
    def __init__(self, pin, sensor_type):
        self.pin = pin; self.sensor_type = sensor_type
        import dht
        if sensor_type == 'DHT22': self.dht = dht.DHT22(pin)
        else: self.dht = dht.DHT11(pin)
        time.sleep_ms(1000)
    
    def measure(self):
        try:
            from machine import disable_irq, enable_irq
            irq_state = disable_irq()
            try: self.dht.measure()
            finally: enable_irq(irq_state)
            return True
        except Exception: return False
    
    def get_temperature(self): return self.dht.temperature()
    def get_humidity(self): return self.dht.humidity()
    def test_read(self):
        try: return self.measure()
        except: return False

class SimulatedDHTDriver:
    def __init__(self, pin, sensor_type):
        self.pin = pin; self.sensor_type = sensor_type; self.counter = 0
        self.base_temp = 27; self.base_humi = 75
    def measure(self): self.counter += 1; return True
    def get_temperature(self): return self.base_temp + int(((self.counter % 10) - 5) * 0.6)
    def get_humidity(self): return self.base_humi + ((self.counter % 8) - 4)
    def test_read(self): return True
