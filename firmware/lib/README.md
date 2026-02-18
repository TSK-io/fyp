# 藏红花培育系统 - 传感器驱动模块

## 📦 模块概述

本模块为藏红花智能培育系统提供了专业的传感器驱动程序，采用分层架构设计，支持多种驱动方式的自动降级机制。

### 🎯 核心特性

- **智能驱动选择**: 硬件级 → 软件级 → 模拟数据的自动降级
- **统一接口**: 所有传感器使用相同的API接口
- **完善的错误处理**: 详细的异常处理和状态监控
- **模块化设计**: 清晰的代码结构，易于维护和扩展
- **生产就绪**: 适用于原型开发和生产环境

### 📊 支持的传感器

- **DHT11/DHT22**: 温湿度传感器（3种驱动模式）
- **更多传感器**: 预留扩展接口

### 🔧 驱动模式

| 模式 | 描述 | 优先级 | 适用场景 |
|------|------|--------|----------|
| **硬件级** | 使用`machine.dht_readinto`硬件函数 | 🥇 最高 | STM32等支持硬件DHT的平台 |
| **软件级** | 标准MicroPython DHT驱动 | 🥈 中等 | 通用MicroPython平台 |
| **模拟级** | 基于真实数据的模拟 | 🥉 保底 | 演示、测试、硬件故障时 |

---

## 🚀 快速开始

### 基本使用

```python
import machine
from drivers import create_dht11_sensor

# 创建传感器实例
pin = machine.Pin('A1', machine.Pin.IN, machine.Pin.PULL_UP)
sensor = create_dht11_sensor(pin, 'DHT11')

# 读取数据
if sensor.measure():
    data = sensor.get_data()
    print(f"温度: {data['temperature']}°C")
    print(f"湿度: {data['humidity']}%")
    print(f"驱动: {data['driver_mode']}")
```

### 完整示例

```python
import machine
import time
import json
from drivers import create_dht11_sensor, get_driver_info

# 获取驱动信息
info = get_driver_info()
print(f"驱动版本: {info['version']}")
print(f"硬件支持: {info['hardware_dht_support']}")

# 初始化传感器
pin = machine.Pin('A1', machine.Pin.IN, machine.Pin.PULL_UP)
dht11 = create_dht11_sensor(pin, 'DHT11')

# 检查传感器状态
if dht11.is_ready():
    print("传感器就绪")
    print(f"使用驱动: {dht11.driver_mode}")
    
    # 数据采集循环
    for i in range(10):
        if dht11.measure():
            data = dht11.get_data()
            
            # 输出JSON格式
            json_data = {
                "temp": data['temperature'],
                "humi": data['humidity'],
                "driver": data['driver_mode'],
                "cycle": i + 1
            }
            print(json.dumps(json_data))
        
        time.sleep(3)
    
    # 显示统计信息
    status = dht11.get_status()
    print(f"成功率: {status['success_rate']}")
```

---

## 📚 API 文档

### 工厂函数

#### `create_dht11_sensor(pin, sensor_type='DHT11')`

创建DHT传感器实例（推荐使用）

**参数:**
- `pin`: MicroPython Pin对象
- `sensor_type`: `'DHT11'` 或 `'DHT22'`

**返回:** `DHT11Sensor` 实例

**示例:**
```python
import machine
from drivers import create_dht11_sensor

pin = machine.Pin('A1', machine.Pin.IN, machine.Pin.PULL_UP)
sensor = create_dht11_sensor(pin, 'DHT11')
```

#### `get_driver_info()`

获取驱动模块信息

**返回:** 包含驱动信息的字典

**示例:**
```python
from drivers import get_driver_info

info = get_driver_info()
print(f"版本: {info['version']}")
print(f"平台: {info['platform']}")
print(f"硬件DHT支持: {info['hardware_dht_support']}")
```

### DHT11Sensor 类

#### 核心方法

##### `measure()`

执行传感器测量

**返回:** `bool` - 是否测量成功

**异常:** `SensorError` - 传感器未就绪时

**示例:**
```python
if sensor.measure():
    print("测量成功")
else:
    print("测量失败")
```

##### `get_data()`

获取传感器数据

**返回:** `dict` - 包含完整传感器数据

**数据结构:**
```python
{
    'temperature': 27,           # 温度值
    'humidity': 75,             # 湿度值  
    'driver_mode': 'hardware',  # 驱动模式
    'sensor_type': 'DHT11',     # 传感器类型
    'timestamp': 12345678,      # 时间戳
    'is_valid': True            # 数据是否有效
}
```

##### `get_temperature()` / `get_humidity()`

获取单独的温湿度值

**返回:** `int`/`float` - 温度或湿度值

#### 状态方法

##### `is_ready()`

检查传感器是否就绪

**返回:** `bool`

##### `get_status()`

获取详细状态信息

**返回:** `dict` - 包含状态、统计等信息

**状态结构:**
```python
{
    'sensor_type': 'DHT11',
    'pin': 'Pin(Pin.cpu.A1, mode=Pin.IN, pull=Pin.PULL_UP)',
    'is_initialized': True,
    'is_available': True,
    'is_ready': True,
    'read_count': 150,
    'error_count': 5,
    'success_rate': '96.7%',
    'last_read_time': 12345678,
    'last_error': None
}
```

##### `reset_statistics()`

重置统计信息

**示例:**
```python
sensor.reset_statistics()
print("统计已重置")
```

#### 属性

- `driver_mode`: 当前驱动模式 (`'hardware'`, `'software'`, `'simulated'`)
- `sensor_type`: 传感器类型
- `temperature`: 最后读取的温度值
- `humidity`: 最后读取的湿度值

---

## 🏗️ 模块结构

```
drivers/
├── __init__.py          # 模块入口，公开API
├── sensor_base.py       # 传感器基类
├── dht11.py            # DHT11/DHT22驱动实现
└── README.md           # 本文档
```

### 架构设计

```
┌─────────────────┐
│   用户代码       │
├─────────────────┤
│   工厂函数       │  create_dht11_sensor()
├─────────────────┤
│  DHT11Sensor    │  统一接口层
├─────────────────┤
│  具体驱动实现    │  Hardware/Software/Simulated
├─────────────────┤
│   传感器基类     │  SensorBase
├─────────────────┤
│   硬件抽象层     │  MicroPython Pin/machine
└─────────────────┘
```

---

## 🔧 驱动开发

### 扩展新传感器

1. **继承基类**
```python
from .sensor_base import SensorBase, SensorError

class MySensor(SensorBase):
    def __init__(self, pin):
        super().__init__(pin, "MySensor")
        # 初始化代码
    
    def measure(self):
        # 测量逻辑
        pass
    
    def get_data(self):
        # 数据获取逻辑
        pass
```

2. **注册到模块**
```python
# 在 __init__.py 中添加
from .mysensor import MySensor
__all__.append('MySensor')

def create_my_sensor(pin):
    return MySensor(pin)
```

### 驱动实现规范

- **继承SensorBase**: 确保接口一致性
- **实现必须方法**: `measure()`, `get_data()`
- **错误处理**: 使用`SensorError`异常
- **状态管理**: 调用`_update_read_stats()`
- **日志记录**: 使用`_log_info()`, `_log_error()`, `_log_success()`

---

## ⚠️ 注意事项

### 硬件级驱动要求

- **平台支持**: 需要`machine.dht_readinto`函数
- **固件版本**: 推荐MicroPython v1.20+
- **引脚配置**: 确保引脚支持数字I/O

### 常见问题

#### Q: 驱动自动降级是什么意思？
A: 当高优先级驱动失败时，系统会自动尝试低优先级驱动，确保系统始终可用。

#### Q: 模拟数据的范围是什么？
A: 基于真实测试数据：温度25-30°C，湿度70-80%，有自然变化。

#### Q: 如何判断当前使用的驱动模式？
A: 查看`sensor.driver_mode`属性或`get_data()`返回的`driver_mode`字段。

#### Q: 成功率多少算正常？
A: 硬件级驱动>95%，软件级驱动>80%，模拟驱动100%。

---

## 📈 版本历史

- **v1.0.0** - 初始版本，支持DHT11/DHT22三级驱动模式

---

## 🤝 贡献指南

1. 遵循现有代码风格
2. 为新功能添加测试
3. 更新文档
4. 确保向后兼容性

---

## 📄 许可证

本模块是藏红花智能培育系统的一部分，遵循项目整体许可证。
