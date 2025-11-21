import gc
import time

import machine

try:
    import uasyncio
except ImportError:
    print("!!!!! 致命错误: 找不到 uasyncio 库! !!!!!")
    uasyncio = None

import config
import dht_sensor
import display
import hardware
import network_manager
import nfc_reader


async def task_nfc_loop(readers, config_data):
    """
    异步任务：轮询 NFC 读卡器。
    """
    if config.DEBUG:
        print("DEBUG: (Async) NFC 轮询任务已启动。")

    reader_count = len(readers)
    current_slot_states = [""] * reader_count
    slot_miss_counters = [0] * reader_count
    is_first_loop = True

    nfc_topic_base = config_data.get("nfc_mqtt_topic_base")

    nfc_topics = [f"{nfc_topic_base}/slot_{i+1}" for i in range(reader_count)]

    local_set_led = hardware.set_led
    local_read_tag = nfc_reader.read_tag_text
    local_publish = network_manager.try_publish_mqtt

    while True:
        if config.DEBUG:
            print(f"\nDEBUG: --- (Async) RFID 循环开始 (Time: {time.time()}) ---")

        local_set_led(0, 255, 0)  # 调用局部变量 (绿色)

        for i in range(reader_count):
            reader = readers[i]
            slot_number = i + 1
            if config.DEBUG:
                print(f"DEBUG: 正在轮询 Slot {slot_number}...")

            local_set_led(255, 255, 0)  # 调用局部变量 (黄色)
            detected_text = local_read_tag(reader) 
            local_set_led(0, 255, 0)  # 调用局部变量 (绿色)

            if detected_text:
                # 成功读到标签（ID），如果与当前记录不同或首次循环则更新并发布
                if detected_text != current_slot_states[i] or is_first_loop:
                    if config.DEBUG:
                        print(
                            f"DEBUG: Slot {slot_number}: *** 状态确认/变更 *** ID: '{detected_text}'"
                        )
                    current_slot_states[i] = detected_text
                    slot_miss_counters[i] = 0
                    # 发布已检测到的 ID
                    local_publish(nfc_topics[i], detected_text)
                else:
                    # 读到同一标签，重置失败计数
                    slot_miss_counters[i] = 0

            else:
                # 没有读到标签
                if current_slot_states[i] == "":
                    # 本来就是空盘，且不是首次循环，不需要任何操作
                    if is_first_loop:
                        # 首次循环时仍然发布空状态以完成初始化
                        if config.DEBUG:
                            print(
                                f"DEBUG: Slot {slot_number}: 首次循环，发布空状态初始化"
                            )
                        local_publish(nfc_topics[i], "")
                else:
                    # 之前有标签，现在读不到，增加失败计数；达到阈值后才发布空盘
                    slot_miss_counters[i] += 1
                    if config.DEBUG:
                        print(
                            f"DEBUG: Slot {slot_number}: 未扫到标签, 失败计数: {slot_miss_counters[i]}/{config.NFC_MAX_READ_FAILURES}"
                        )

                    if slot_miss_counters[i] >= config.NFC_MAX_READ_FAILURES:
                        if config.DEBUG:
                            print(
                                f"DEBUG: Slot {slot_number}: --- 标签移除 (已确认) ---"
                            )
                        current_slot_states[i] = ""
                        slot_miss_counters[i] = 0
                        # 发布空盘状态
                        local_publish(nfc_topics[i], "")

        if is_first_loop:
            if config.DEBUG:
                print("DEBUG: ===== 首次启动循环完成, 恢复正常轮询模式 =====")
            is_first_loop = False

        if config.DEBUG:
            print(
                f"DEBUG: --- (Async) RFID 循环结束，休眠 {config.NFC_LOOP_DELAY_MS}ms ---"
            )

        # 非阻塞休眠
        await uasyncio.sleep_ms(config.NFC_LOOP_DELAY_MS)


async def task_dht_loop(dht_sensor_instance, config_data):
    """
    (Async Task) 异步任务：每 10 秒读取 DHT 传感器。
    """
    if config.DEBUG:
        print("DEBUG: (Async) DHT 读取任务已启动。")

    mqtt_topic_temp = config_data.get("mqtt_topic_temp")
    mqtt_topic_humidity = config_data.get("mqtt_topic_humidity")

    # 将函数缓存在局部变量中
    local_read_dht = dht_sensor.read_dht
    local_publish = network_manager.try_publish_mqtt
    local_show_status = display.oled_show_status

    while True:
        temp, hum = local_read_dht()

        if temp is not None and hum is not None:
            # 发布 MQTT 
            local_publish(mqtt_topic_temp, temp)
            local_publish(mqtt_topic_humidity, hum)

        # 更新 OLED 
        local_show_status(temp, hum)

        # 非阻塞休眠
        await uasyncio.sleep(config.DHT_READ_INTERVAL_S)


async def task_button_check():
    """
    (Async Task) 异步任务：高频检查重置按钮。
    """
    if config.DEBUG:
        print("DEBUG: (Async) 重置按钮监控任务已启动。")

    local_check_button = hardware.check_reset_button
    local_show_message = display.oled_show_message

    while True:
        local_check_button(local_show_message)

        await uasyncio.sleep_ms(config.BUTTON_CHECK_MS)


def main():
    """
    主启动函数
    """
    gc.collect()  # 初始内存清理

    print("===============================")
    print("  ESP32 AMS Sensor (V40-Async)")
    print("===============================")

    # 1. 初始化核心硬件
    hardware.init_led()
    hardware.init_reset_button()
    display.init_oled()

    hardware.set_led(255, 0, 0)  # 红色 (启动中)
    display.oled_show_message("系统启动中...")

    # 2. 加载配置
    config_data = config.load_config()

    # 3. 初始化网络
    network_manager.init_mqtt(config_data)

    wifi_ssid = config_data.get("wifi_ssid")
    wifi_pass = config_data.get("wifi_pass")

    if network_manager.connect_wifi(wifi_ssid, wifi_pass, display_module=display):

        # --- 4a. 正常模式 (WiFi 连接成功) ---
        if config.DEBUG:
            print("DEBUG: WiFi 连接成功，进入正常模式...")
        hardware.set_led(0, 255, 0)  # 绿色

        # 连接 MQTT
        network_manager.connect_mqtt(display_module=display)

        # 初始化传感器
        readers = nfc_reader.init_readers()
        dht_sensor_instance = dht_sensor.init_dht()

        if not readers:
            print("!!!!! 致命错误: 没有任何 NFC 读卡器初始化成功，停止。 !!!!!")
            display.oled_show_message("NFC 启动失败", "请重启")
            return  # 停止运行

        gc.collect()  # 在启动主循环前清理内存

        # 启动 Async 任务
        if uasyncio:
            try:
                loop = uasyncio.get_event_loop()
                # 创建任务
                loop.create_task(task_nfc_loop(readers, config_data))
                loop.create_task(task_dht_loop(dht_sensor_instance, config_data))
                loop.create_task(task_button_check())
                # 启动事件循环
                if config.DEBUG:
                    print("DEBUG: ===== (Async) 启动主事件循环 =====")
                loop.run_forever()
            except Exception as e:
                print(f"!!!!! 致命错误: Asyncio 循环失败: {e} !!!!!")
                machine.reset()
        else:
            print("!!!!! 致命错误: uasyncio 未加载! !!!!!")
            display.oled_show_message("系统错误", "uasyncio 丢失")

    else:
        # --- 4b. 配置模式 (WiFi 连接失败) ---
        print("!!!!! WiFi 连接失败，启动配置模式... !!!!!")
        hardware.set_led(255, 0, 0)  # 红色 (配置模式)
        display.oled_show_config_mode()

        gc.collect()  # 在导入 Web 服务器前清理内存

        try:
            # 仅在此时导入重量级的 config_server
            import config_server

            if config.DEBUG:
                print("DEBUG: 启动配置服务器...")
            # 启动阻塞的 Web 服务器
            config_server.start_config_server(
                config_data, display, hardware.check_reset_button
            )
        except ImportError:
            print("!!!!! 致命错误: 缺少 config_server.py !!!!!")
            display.oled_show_message("启动失败", "缺少文件")
        except Exception as e:
            print(f"!!!!! 致命错误: 配置服务器启动失败: {e} !!!!!")
            display.oled_show_message("服务器错误", str(e)[:16])


# --- 启动 ---
if __name__ == "__main__":
    main()
