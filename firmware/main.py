# 藏红花培育系统主程序 - v10.0 (结构重构版)
# 适配 /lib 扁平化目录结构

import machine
import time
import json
import sys
import select

# --- 导入驱动模块 (直接从 /lib 导入) ---
try:
    # 以前是 from drivers import ..., 现在直接 import
    import ssd1306
    from paj7620 import PAJ7620
    from dht11 import DHT11Sensor 
    
    # BH1750 类直接内嵌，保持简单
    class BH1750:
        def __init__(self, i2c, addr=0x23):
            self.i2c = i2c; self.addr = addr; self.is_initialized = False
            try:
                self.i2c.writeto(self.addr, b'\x01'); time.sleep_ms(10)
                self.i2c.writeto(self.addr, b'\x10'); time.sleep_ms(120)
                self.is_initialized = True
            except Exception as e: print(f"BH1750 初始化失败: {e}")
        def read_lux(self):
            if not self.is_initialized: return None
            try:
                data = self.i2c.readfrom(self.addr, 2)
                return ((data[0] << 8) | data[1]) / 1.2
            except: return None

    print("所有驱动模块加载成功")
except ImportError as e:
    print(f"关键驱动模块导入失败: {e}")
    # 为了防止死循环重启，这里可以闪灯报错，或者sys.exit
    sys.exit()

print("\n=== 藏红花培育系统 v10.0 ===")

# --- 全局状态管理 ---
# OLED 共有 3 个页面: 主页、控制页、信息页。
SCREEN_WIDTH = 128
SCREEN_HEIGHT = 64
I2C_ADDRESS = 0x3C
current_display_page = 0
NUM_PAGES = 3
control_page_selection = 0
NUM_CONTROL_ITEMS = 3 

# --- 硬件初始化 ---
status_led = machine.Pin('C13', machine.Pin.OUT, value=1)
dht11, light_sensor, soil_adc, paj_sensor = None, None, None, None
pump_relay, led_strip_relay = None, None
display = None

# --- 智能执行器策略参数 ---
LED_STRIP_ON_LUX = 120
LED_STRIP_OFF_LUX = 180
LED_STRIP_EVAL_INTERVAL_MS = 5000

smart_state = {
    'warning_auto_enabled': True,
    'warning_level': 'unknown',
    'warning_blink_on': False,
    'warning_last_level': None,
    'warning_next_toggle': 0,
    'strip_auto_enabled': True,
    'strip_next_eval': 0,
}

# 初始化 DHT11
try: 
    # 直接实例化，不再使用工厂函数
    dht11 = DHT11Sensor(machine.Pin('A1', machine.Pin.IN, machine.Pin.PULL_UP), 'DHT11')
except Exception as e: print(f"DHT11 初始化失败: {e}")

# 初始化 I2C 设备
try:
    # 该 I2C 总线同时挂载光照、OLED 和手势模块，因此初始化失败会影响多个功能。
    i2c = machine.I2C(1, freq=200000)
    print("I2C 总线初始化成功")
    
    light_sensor = BH1750(i2c)
    
    display = ssd1306.SSD1306_I2C(SCREEN_WIDTH, SCREEN_HEIGHT, i2c, I2C_ADDRESS)
    print("OLED 显示屏初始化成功")
    
    paj_sensor = PAJ7620(i2c)
    paj_sensor.init()
    print("PAJ7620 手势传感器初始化成功")
    
    display.fill(0)
    display.text('Saffron System', 8, 16)
    display.text('Init OK!', 30, 32)
    display.show()
    time.sleep(1)
except Exception as e:
    print(f"I2C设备(光照/OLED/手势)初始化失败: {e}")

# 初始化模拟传感器和执行器
try: soil_adc = machine.ADC(machine.Pin('A2'))
except Exception as e: print(f"土壤湿度传感器初始化失败: {e}")

try:
    pump_relay = machine.Pin('B10', machine.Pin.OUT, value=0)
    print("水泵继电器(B10)初始化成功")
except Exception as e: print(f"水泵继电器初始化失败: {e}")

try:
    led_strip_relay = machine.Pin('B12', machine.Pin.OUT, value=0)
    print("LED灯带继电器(B12)初始化成功")
except Exception as e: print(f"LED灯带继电器初始化失败: {e}")

# --- 智能控制辅助逻辑 ---
def _set_status_led(on):
    if status_led:
        status_led.value(0 if on else 1)

def _compute_warning_level(data):
    score = 0

    temp = data.get('temp')
    humi = data.get('humi')
    soil = data.get('soil')

    if temp is None or humi is None or soil is None:
        score += 1

    if temp is not None:
        if temp < 10 or temp > 32:
            score += 2
        elif temp < 14 or temp > 28:
            score += 1

    if humi is not None:
        if humi < 25 or humi > 90:
            score += 2
        elif humi < 35 or humi > 80:
            score += 1

    if soil is not None:
        if soil < 25:
            score += 2
        elif soil < 35:
            score += 1

    if score >= 4:
        return 'high'
    if score >= 2:
        return 'medium'
    return 'low'

def apply_warning_led_policy(data, now_ms):
    if not status_led:
        return

    if not smart_state['warning_auto_enabled']:
        return

    level = _compute_warning_level(data)
    smart_state['warning_level'] = level

    if level != smart_state['warning_last_level']:
        smart_state['warning_last_level'] = level
        smart_state['warning_blink_on'] = False
        smart_state['warning_next_toggle'] = 0

    if level == 'low':
        _set_status_led(False)
        smart_state['warning_blink_on'] = False
        return

    interval = 200 if level == 'high' else 700
    if time.ticks_diff(now_ms, smart_state['warning_next_toggle']) >= 0:
        smart_state['warning_blink_on'] = not smart_state['warning_blink_on']
        _set_status_led(smart_state['warning_blink_on'])
        smart_state['warning_next_toggle'] = time.ticks_add(now_ms, interval)

def apply_led_strip_policy(data, now_ms):
    if not led_strip_relay:
        return

    if not smart_state['strip_auto_enabled']:
        return
    if time.ticks_diff(now_ms, smart_state['strip_next_eval']) < 0:
        return

    smart_state['strip_next_eval'] = time.ticks_add(now_ms, LED_STRIP_EVAL_INTERVAL_MS)
    lux = data.get('lux')
    if lux is None:
        return

    current_on = bool(led_strip_relay.value())
    if (not current_on) and lux <= LED_STRIP_ON_LUX:
        led_strip_relay.high()
    elif current_on and lux >= LED_STRIP_OFF_LUX:
        led_strip_relay.low()

# --- OLED 显示逻辑 ---
def update_display(data, page_num):
    if not display: return
    display.fill(0)
    
    page_indicator = f"[{page_num + 1}/{NUM_PAGES}]"
    indicator_x = 128 - len(page_indicator) * 8 - 2
    
    title = " "
    if page_num == 0: title = "MAIN"
    elif page_num == 1: title = "CTRL"
    elif page_num == 2: title = "INFO"
    display.text(title, 4, 0)
    display.text(page_indicator, indicator_x, 0)
    display.text("----------------", 0, 9)

    if page_num == 0:
        # 主页面展示树莓派最关心的一组实时感知数据。
        temp_str = f"T:{data.get('temp', '--')}C"; humi_str = f"H:{data.get('humi', '--')}%"
        lux_str  = f"L:{data.get('lux', '--')}"; soil_str = f"S:{data.get('soil', '--')}%"
        display.text(temp_str, 0, 19); display.text(humi_str, 64, 19)
        display.text(lux_str, 0, 35);  display.text(soil_str, 64, 35)
        display.text(f"Ges: {data.get('gesture', '--')}", 0, 55)

    elif page_num == 1:
        # 控制页允许通过手势直接切换本地执行器状态。
        pump_state = "ON" if pump_relay and pump_relay.value() else "OFF"
        led_strip_state = "ON" if led_strip_relay and led_strip_relay.value() else "OFF"
        status_led_state = "ON" if status_led and not status_led.value() else "OFF"
        strip_mode = "AUTO" if smart_state['strip_auto_enabled'] else "MAN"
        warning_mode = "AUTO" if smart_state['warning_auto_enabled'] else "MAN"
        
        pump_line = f"{'>' if control_page_selection == 0 else ' '} Pump  : {pump_state}"
        led_strip_line = f"{'>' if control_page_selection == 1 else ' '} Strip : {led_strip_state}/{strip_mode}"
        status_led_line = f"{'>' if control_page_selection == 2 else ' '} LED   : {status_led_state}/{warning_mode}"
        
        display.text(pump_line, 0, 18)
        display.text(led_strip_line, 0, 31)
        display.text(status_led_line, 0, 44)
        display.text("U/D:Sel L/R:Pg", 0, 55)

    elif page_num == 2:
        # 信息页偏向调试用途，用于确认驱动模式和固件运行状态。
        driver_mode = dht11.driver_mode if dht11 else "N/A"
        display.text(f"DHT: {driver_mode}", 0, 20)
        display.text(f"Loop: {data.get('cycle', 0)}", 0, 34)
        py_ver = f"{sys.version_info[0]}.{sys.version_info[1]}"
        display.text(f"uPy: v{py_ver}", 0, 48)

    display.show()

# --- 命令处理 ---
def process_command(cmd):
    cmd = cmd.strip()
    try:
        # 新版串口协议使用 JSON，便于边缘服务器统一扩展执行器命令。
        data = json.loads(cmd)
        actuator, action = data.get('actuator'), data.get('action')
        response = None
        if actuator == 'pump' and pump_relay:
            if action == 'on': pump_relay.high(); response = '{"response": "Pump is ON"}'
            elif action == 'off': pump_relay.low(); response = '{"response": "Pump is OFF"}'
        elif actuator == 'led_strip' and led_strip_relay:
            if action == 'on':
                led_strip_relay.high()
                smart_state['strip_auto_enabled'] = False
                response = '{"response": "LED Strip is ON (manual mode)"}'
            elif action == 'off':
                led_strip_relay.low()
                smart_state['strip_auto_enabled'] = False
                response = '{"response": "LED Strip is OFF (manual mode)"}'
            elif action == 'manual':
                smart_state['strip_auto_enabled'] = False
                response = '{"response": "LED Strip switched to manual mode"}'
            elif action == 'auto':
                smart_state['strip_auto_enabled'] = True
                response = '{"response": "LED Strip auto mode resumed"}'
        elif actuator == 'status_led' and status_led:
            if action == 'on':
                _set_status_led(True)
                smart_state['warning_auto_enabled'] = False
                response = '{"response": "Status LED is ON (manual mode)"}'
            elif action == 'off':
                _set_status_led(False)
                smart_state['warning_auto_enabled'] = False
                response = '{"response": "Status LED is OFF (manual mode)"}'
            elif action == 'manual':
                smart_state['warning_auto_enabled'] = False
                response = '{"response": "Status LED switched to manual mode"}'
            elif action == 'auto':
                smart_state['warning_auto_enabled'] = True
                response = '{"response": "Status LED auto mode resumed"}'
        if response: print(response)
        else: print('{"error": "Unknown or unavailable actuator"}')
    except (ValueError, KeyError):
        # 保留旧版 status LED 简写命令，兼容现有 Web 前端。
        if cmd == "led_on":
            _set_status_led(True)
            smart_state['warning_auto_enabled'] = False
            print('{"response": "Status LED is ON (manual mode)"}')
        elif cmd == "led_off":
            _set_status_led(False)
            smart_state['warning_auto_enabled'] = False
            print('{"response": "Status LED is OFF (manual mode)"}')
        else: print(f'{{"error": "Unknown command: {cmd}"}}')

# --- 主循环 ---
print("\n开始主循环 (Root版)...")
print("-" * 50)
cycle_count = 0; last_sensor_read_time = time.ticks_ms();
poll_obj = select.poll(); poll_obj.register(sys.stdin, select.POLLIN)
last_valid_gesture = None; gesture_display_timer = 0; GESTURE_TIMEOUT = 3000
last_gesture_process_time = 0; GESTURE_COOLDOWN = 500
current_data_packet = {"cycle": 0, "gesture": None}

while True:
    current_time = time.ticks_ms()

    apply_warning_led_policy(current_data_packet, current_time)
    apply_led_strip_policy(current_data_packet, current_time)
    
    # 手势处理
    if paj_sensor and time.ticks_diff(current_time, last_gesture_process_time) > GESTURE_COOLDOWN:
        try:
            gesture_name = paj_sensor.get_gesture_name(paj_sensor.get_gesture_code())
            if gesture_name:
                last_valid_gesture = gesture_name; gesture_display_timer = current_time; last_gesture_process_time = current_time
                needs_display_update = False
                
                # 左右手势用于翻页；控制页中再用前后/上下做选择和触发。
                if gesture_name == "向右": 
                    current_display_page = (current_display_page + 1) % NUM_PAGES
                    needs_display_update = True
                elif gesture_name == "向左": 
                    current_display_page = (current_display_page - 1 + NUM_PAGES) % NUM_PAGES
                    needs_display_update = True
                elif current_display_page == 1: # 在控制页
                    if gesture_name == "向前": control_page_selection = (control_page_selection + 1) % NUM_CONTROL_ITEMS
                    elif gesture_name == "向后": control_page_selection = (control_page_selection - 1 + NUM_CONTROL_ITEMS) % NUM_CONTROL_ITEMS
                    elif gesture_name in ("向上", "向下"): # 触发动作
                        if control_page_selection == 0 and pump_relay: pump_relay.value(not pump_relay.value())
                        elif control_page_selection == 1 and led_strip_relay:
                            led_strip_relay.value(not led_strip_relay.value())
                            smart_state['strip_auto_enabled'] = False
                        elif control_page_selection == 2 and status_led:
                            current_on = not bool(status_led.value())
                            _set_status_led(not current_on)
                            smart_state['warning_auto_enabled'] = False
                    needs_display_update = True
                
                if needs_display_update: update_display(current_data_packet, current_display_page)
        except Exception: pass

    # 串口命令处理
    if poll_obj.poll(0):
        command = sys.stdin.readline()
        if command: 
            process_command(command)
            if current_display_page == 1: update_display(current_data_packet, current_display_page)

    # 传感器读取循环 (1秒一次)
    if time.ticks_diff(current_time, last_sensor_read_time) >= 1000:
        last_sensor_read_time = current_time; cycle_count += 1
        
        # 手势只在短时间窗口内回传给树莓派，避免旧手势长期滞留在 UI 上。
        current_gesture_for_pi = last_valid_gesture if (last_valid_gesture and time.ticks_diff(current_time, gesture_display_timer) < GESTURE_TIMEOUT) else None
        if not current_gesture_for_pi: last_valid_gesture = None
        
        current_data_packet = {"cycle": cycle_count, "timestamp": time.ticks_ms(), "gesture": current_gesture_for_pi} 
                       
        if dht11 and dht11.measure():
            sensor_data = dht11.get_data()
            if sensor_data.get('is_valid'): 
                current_data_packet.update({'temp': sensor_data.get('temperature'), 'humi': sensor_data.get('humidity')})
        
        if light_sensor: 
            lux = light_sensor.read_lux()
            current_data_packet['lux'] = round(lux, 1) if lux is not None else None
            
        if soil_adc:
            try:
                # 通过经验干湿标定值把 ADC 原始读数映射到 0-100%。
                raw, DRY, WET = soil_adc.read_u16(), 59000, 26000
                if WET <= raw <= DRY + 2000: 
                    current_data_packet['soil'] = round(max(0, min(100, 100 * (DRY - raw) / (DRY - WET))))
            except: pass

        current_data_packet['warning_level'] = smart_state['warning_level']
        current_data_packet['strip_auto'] = smart_state['strip_auto_enabled']
        current_data_packet['warning_auto'] = smart_state['warning_auto_enabled']
                
        print(json.dumps(current_data_packet))
        update_display(current_data_packet, current_display_page)
        
    time.sleep_ms(20)
