import ujson
import os

# --- 1. 调试与性能 ---
DEBUG = True  # 设置为 False 可禁用所有调试 print 语句

# --- 2. 硬件引脚定义 (UPPER_SNAKE_CASE) ---
PIN_NEOPIXEL = 48
PIN_DHT = 13
PIN_OLED_SCL = 9
PIN_OLED_SDA = 8
PIN_BOOT_BUTTON = 0

# MFRC522 读卡器引脚配置
# (sck=5, mosi=6, miso=7 是共享的 SPI 总线)
READER_PINS = [
    {"rst": 15, "cs": 4},  # 读卡器 1
    {"rst": 3, "cs": 16},  # 读卡器 2
    {"rst": 12, "cs": 46}, # 读卡器 3
    {"rst": 35, "cs": 38}, # 读卡器 4
]
READER_SPI_SHARED = {"sck": 5, "mosi": 6, "miso": 7}

# --- 3. 网络配置 ---
CONFIG_FILE = "config.json"
AP_SSID = "AMS-Sensor"
AP_IP = "10.1.1.1"
AP_NETMASK = "255.255.255.0"

# --- 4. 异步任务与循环延时 ---
BUTTON_CHECK_MS = 50       # 按钮检查间隔
NFC_LOOP_DELAY_MS = 1500   # NFC 轮询间隔
DHT_READ_INTERVAL_S = 10   # DHT 读取间隔
NFC_MAX_READ_FAILURES = 200 # NFC 标签移除确认阈值

# --- 5. 默认配置 ---
DEFAULT_CONFIG = {
    "wifi_ssid": "",
    "wifi_pass": "",
    "nfc_mqtt_topic_base": "ams_sensor/nfc",
    "mqtt_broker": "",
    "mqtt_port": 1883,
    "mqtt_user": "",
    "mqtt_pass": "",
    "mqtt_client_id": "ams-sensor",
    "mqtt_topic_temp": "ams_sensor/temperature",
    "mqtt_topic_humidity": "ams_sensor/humidity",
}

# --- 6. 配置管理函数 ---

def load_config():
    """
    加载 config.json
    """
    try:
        with open(CONFIG_FILE, "r") as f:
            config_data = ujson.load(f)
            
        migrated = False
        # 确保所有键都存在
        for key in DEFAULT_CONFIG:
            if key not in config_data:
                config_data[key] = DEFAULT_CONFIG[key]
                migrated = True

        # 旧版配置文件迁移
        old_keys = ["webhook_url", "nfc_mqtt_enabled", "dht_mqtt_enabled", "mqtt_enabled"]
        for key in old_keys:
            if key in config_data:
                del config_data[key]
                migrated = True

        if migrated:
            if DEBUG: print("DEBUG: 检测到旧配置，已迁移并保存。")
            save_config(config_data)
            
        if DEBUG: print("DEBUG: 配置已从 config.json 加载。")
        return config_data
        
    except (OSError, ValueError):
        if DEBUG: print("DEBUG: 未找到配置文件或已损坏，创建默认配置...")
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

def save_config(config_to_save):
    """
    将配置字典保存到 config.json。
    """
    try:
        with open(CONFIG_FILE, "w") as f:
            ujson.dump(config_to_save, f)
        if DEBUG: print("DEBUG: 配置已保存到 config.json。")
    except Exception as e:
        print(f"!!!!! 错误: 保存配置失败: {e} !!!!!")