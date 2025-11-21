from machine import I2C, Pin
import config 

try:
    import pf  # 字体文件
    import ssd1306
    from writer import Writer
except ImportError as e:
    print(f"!!!!! 致命错误: 缺少OLED库文件: {e} !!!!!")
    class MockSSD1306:
        def __init__(self, *args, **kwargs): pass
        def fill(self, *args, **kwargs): pass
        def show(self, *args, **kwargs): pass
    
    class MockWriter:
        def __init__(self, *args, **kwargs): pass
        def printstring(self, *args, **kwargs): pass
        @staticmethod
        def set_textpos(*args, **kwargs): pass

    ssd1306 = MockSSD1306
    Writer = MockWriter
    pf = None

# --- 模块全局变量 ---
_oled = None
_writer = None

def init_oled():
    """初始化 SSD1306 OLED 屏幕。"""
    global _oled, _writer
    
    if pf is None:
        print("!!!!! 警告: 因缺少库，OLED 功能已禁用。 !!!!!")
        return False
        
    try:
        i2c = I2C(0, scl=Pin(config.PIN_OLED_SCL), sda=Pin(config.PIN_OLED_SDA))
        _oled = ssd1306.SSD1306_I2C(128, 64, i2c)
        _oled.fill(0)
        _writer = Writer(_oled, pf)
        if config.DEBUG:
            print(
                f"DEBUG: SSD1306 OLED (128x64) I2C at SCL={config.PIN_OLED_SCL}, SDA={config.PIN_OLED_SDA} 初始化成功。"
            )
        oled_show_message("系统启动中...")
        return True
    except Exception as e:
        if "ENODEV" in str(e):
            print("!!!!! 警告: OLED 初始化失败: [Errno 19] ENODEV !!!!!")
        else:
            print(f"!!!!! 警告: OLED 初始化失败: {e} !!!!!")
        _oled = None
        _writer = None
        return False

def oled_show_message(line1, line2=""):
    """在 OLED 上显示两行消息。"""
    if _writer:
        try:
            _oled.fill(0)
            Writer.set_textpos(_oled, 8, 0)
            _writer.printstring(line1)
            Writer.set_textpos(_oled, 36, 0)
            _writer.printstring(line2)
            _oled.show()
        except Exception as e:
            if config.DEBUG: print(f"DEBUG: OLED show_message 失败: {e}")

def oled_show_status(temp=None, hum=None):
    """显示温湿度状态。"""
    if _writer:
        try:
            _oled.fill(0)
            temp_str = f"温度: {temp:.1f}C" if temp is not None else "温度: --"
            hum_str = f"湿度: {hum:.1f}%" if hum is not None else "湿度: --"
            Writer.set_textpos(_oled, 8, 0)
            _writer.printstring(temp_str)
            Writer.set_textpos(_oled, 36, 0)
            _writer.printstring(hum_str)
            _oled.show()
        except Exception as e:
            if config.DEBUG: print(f"DEBUG: OLED show_status 失败: {e}")

def oled_show_config_mode():
    """显示配置模式 (AP) 界面。"""
    if _writer:
        try:
            _oled.fill(0)
            Writer.set_textpos(_oled, 0, 0)
            _writer.printstring("配置模式")
            Writer.set_textpos(_oled, 22, 0)
            _writer.printstring(f"热点{config.AP_SSID}")
            Writer.set_textpos(_oled, 44, 0)
            _writer.printstring(f"IP: {config.AP_IP}")
            _oled.show()
        except Exception as e:
            if config.DEBUG: print(f"DEBUG: OLED config_mode 失败: {e}")