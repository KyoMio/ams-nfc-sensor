import machine
import neopixel
import time
import os

import config

# --- 模块全局变量 ---
_led_instance = None
_button_pin = None
_button_press_start_ms = 0

BRIGHTNESS = 20 # LED 亮度

def init_led():
    """初始化 NeoPixel LED。"""
    global _led_instance
    try:
        _led_instance = neopixel.NeoPixel(machine.Pin(config.PIN_NEOPIXEL), 1)
        set_led(0, 0, 0) # 默认为关闭
        if config.DEBUG: 
            print(f"DEBUG: 板载 Neopixel LED 已在 Pin {config.PIN_NEOPIXEL} 初始化")
    except Exception as e:
        print(f"!!!!! 警告: Neopixel LED 初始化失败: {e}. (Pin {config.PIN_NEOPIXEL}) !!!!!")

def set_led(r, g, b):
    """设置 NeoPixel LED 颜色。"""
    global _led_instance
    if _led_instance:
        try:
            r_adj = int(r * (BRIGHTNESS / 255.0))
            g_adj = int(g * (BRIGHTNESS / 255.0))
            b_adj = int(b * (BRIGHTNESS / 255.0))
            _led_instance[0] = (r_adj, g_adj, b_adj)
            _led_instance.write()
        except Exception as e:
            if config.DEBUG: print(f"DEBUG: 设置 LED 失败: {e}")

def init_reset_button():
    """初始化 BOOT 按钮 (Pin 0)。"""
    global _button_pin
    try:
        _button_pin = machine.Pin(
            config.PIN_BOOT_BUTTON, machine.Pin.IN, machine.Pin.PULL_UP
        )
        if config.DEBUG:
            print(f"DEBUG: BOOT 按钮 (重置) 将在 Pin {config.PIN_BOOT_BUTTON} 上监控。")
    except Exception as e:
        print(f"!!!!! 警告: 无法初始化 BOOT 按钮 (Pin {config.PIN_BOOT_BUTTON}): {e} !!!!!")
        _button_pin = "failed"

def check_reset_button(oled_message_func):
    """
    检查重置按钮状态，长按10秒清除配置。
    非阻塞，由 async 任务高频调用。
    依赖注入：传入 oled_message_func 来显示消息。
    """
    global _button_press_start_ms, _button_pin
    
    if _button_pin is None or _button_pin == "failed":
        return

    if _button_pin.value() == 0:
        # 按钮被按下
        current_time_ms = time.ticks_ms()
        if _button_press_start_ms == 0:
            # 刚按下
            _button_press_start_ms = current_time_ms
            if config.DEBUG: print("DEBUG: 重置按钮被按下。请长按10秒以清除配置...")
            oled_message_func("长按以重置...", "") 
            
        elif time.ticks_diff(current_time_ms, _button_press_start_ms) > 10000:
            # 按下已超过10秒
            print("!!!!! 触发10秒长按: 正在重置配置 !!!!!")
            oled_message_func("重置配置...", "正在擦除...")
            set_led(255, 0, 255)  # 紫色
            try:
                os.remove(config.CONFIG_FILE)
                if config.DEBUG: print(f"DEBUG: {config.CONFIG_FILE} 已删除。")
            except OSError:
                if config.DEBUG: print(f"DEBUG: {config.CONFIG_FILE} 未找到，无需删除。")
            
            time.sleep(2)
            machine.reset()
            
    else:
        # 按钮未被按下
        if _button_press_start_ms != 0:
            # 刚刚释放
            if config.DEBUG: print("DEBUG: 重置按钮已释放 (未满10秒)。")
        _button_press_start_ms = 0