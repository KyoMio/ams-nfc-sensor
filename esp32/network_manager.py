import network
import time
import config
import display

try:
    from umqtt.simple import MQTTClient
except ImportError:
    print("!!!!! 致命错误: 找不到 umqtt.simple 库! !!!!!")
    MQTTClient = None

# --- 模块全局变量 ---
_mqtt_client = None
_config = None # 存储加载的配置

def connect_wifi(ssid, password, display_module):
    """
    连接到 WiFi。
    依赖注入：传入 display_module 来显示状态。
    """
    if not ssid:
        print("!!!!! 错误: WiFi SSID 未在配置中设置 !!!!!")
        return False
        
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        if config.DEBUG: print(f"DEBUG: 正在连接到 WiFi: {ssid}...")
        display_module.oled_show_message("正在连接WiFi", ssid)
        
        sta_if.active(True)
        sta_if.connect(ssid, password)
        
        timeout = 10
        while not sta_if.isconnected() and timeout > 0:
            if config.DEBUG: print("DEBUG: 等待连接...")
            time.sleep(1)
            timeout -= 1
            
        if not sta_if.isconnected():
            print("!!!!! 错误: WiFi 连接失败 !!!!!")
            return False
            
    if config.DEBUG: print("DEBUG: WiFi 已连接!")
    if config.DEBUG: print(f"DEBUG: IP 地址: {sta_if.ifconfig()[0]}")
    return True

def init_mqtt(loaded_config):
    """存储配置并初始化 MQTT 客户端实例。"""
    global _mqtt_client, _config
    _config = loaded_config
    
    if MQTTClient is None:
        print("!!!!! 错误: MQTT 库未加载，MQTT 将被禁用。")
        return

    broker = _config.get("mqtt_broker")
    if not broker:
        if config.DEBUG: print("MQTT Broker 未配置。跳过 MQTT。")
        return

    try:
        port = int(_config.get("mqtt_port", 1883))
        _mqtt_client = MQTTClient(
            client_id=_config.get("mqtt_client_id"),
            server=broker,
            port=port,
            user=_config.get("mqtt_user", ""),
            password=_config.get("mqtt_pass", ""),
            keepalive=60,
        )
    except Exception as e:
        print(f"!!!!! 错误: 初始化 MQTT 客户端失败: {e} !!!!!")
        _mqtt_client = None


def connect_mqtt(display_module):
    """(重新)连接到 MQTT broker。"""
    global _mqtt_client
    
    if _mqtt_client is None:
        if config.DEBUG: print("DEBUG: MQTT 客户端未初始化 (Broker未配置?)")
        return False

    broker = _config.get("mqtt_broker")
    
    try:
        if config.DEBUG: print(f"Connecting to MQTT broker at {broker}...")
        display_module.oled_show_message("连接 MQTT...", broker)
        _mqtt_client.connect() # 阻塞调用
        print("MQTT 连接成功!")
        display_module.oled_show_message("MQTT 已连接")
        time.sleep(1) # 短暂显示
        return True
    except Exception as e:
        print(f"!!!!! 致命错误: MQTT 连接失败: {e} !!!!!")
        display_module.oled_show_message("MQTT 连接失败", str(e)[:16])
        time.sleep(2)
        return False

def try_publish_mqtt(topic, value):
    """
    尝试发布 MQTT 消息，如果失败则标记重连。
    """
    global _mqtt_client, _config
    
    if _mqtt_client is None or not topic:
        if config.DEBUG and not topic: print("MQTT topic 为空，跳过发布。")
        return

    try:
        _mqtt_client.publish(topic, str(value), retain=True)
        if config.DEBUG: print(f"MQTT Published: {topic} = {value}")
    except Exception as e:
        print(f"!!!!! 错误: MQTT publish 失败: {e}. 标记重连。")
        if _mqtt_client:
            try:
                _mqtt_client.disconnect()
            except Exception:
                pass

        print("MQTT: 正在尝试立即重连...")
        try:
            connect_mqtt(display) 
            print("MQTT: 重连成功。")
            _mqtt_client.publish(topic, str(value), retain=True)
            if config.DEBUG: print(f"MQTT (重试) Published: {topic} = {value}")
        except Exception as e2:
            print(f"!!!!! 错误: MQTT 重连失败: {e2}。等待下一次 publish。")
            _mqtt_client = None 
            init_mqtt(_config)
            

def publish_nfc_state(slot, spool_id):
    """
    将 NFC 状态发送到 MQTT。
    """
    global _config
    if _config is None:
        return

    base_topic = _config.get("nfc_mqtt_topic_base", "ams_sensor/nfc")
    full_topic = f"{base_topic}/slot_{slot}"

    if config.DEBUG: 
        print(f"DEBUG: 正在发布 NFC 状态到 MQTT Topic: {full_topic}")
    
    try_publish_mqtt(full_topic, spool_id)