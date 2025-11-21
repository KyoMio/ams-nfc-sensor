import machine
import config

try:
    import dht
except ImportError:
    print("!!!!! 致命错误: 找不到 dht.py 库! !!!!!")
    dht = None

_dht_sensor = None

def init_dht():
    """初始化 DHT22 传感器。"""
    global _dht_sensor
    if dht is None:
        return None
        
    try:
        _dht_sensor = dht.DHT22(machine.Pin(config.PIN_DHT))
        if config.DEBUG:
            print(f"DEBUG: 内置 dht (DHT22) 传感器已在 Pin {config.PIN_DHT} 初始化。")
        return _dht_sensor
    except Exception as e:
        print(f"!!!!! 警告: DHT22 初始化失败: {e} !!!!!")
        _dht_sensor = None
        return None

def read_dht():
    """读取温湿度，返回 (T, H) 元组。"""
    global _dht_sensor
    if _dht_sensor is None:
        return None, None

    if config.DEBUG: print(f"\nDEBUG: --- 正在读取 DHT22 ---")
    
    try:
        _dht_sensor.measure()
        temp = _dht_sensor.temperature()
        hum = _dht_sensor.humidity()

        if temp is not None and hum is not None:
            if config.DEBUG: print(f"DEBUG: 温度: {temp}°C, 湿度: {hum}%")
            return temp, hum
        else:
            print("!!!!! 错误: DHT22 读取失败 (返回 None)。")
            return None, None
    except Exception as e:
        print(f"!!!!! 错误: 读取 DHT22 时发生异常: {e} !!!!!")
        return None, None