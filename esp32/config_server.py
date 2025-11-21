import machine
import network
import time
import ujson
import usocket
import micropython 

import config 

@micropython.native 
def _unquote_plus(s):
    """用于解析 URL 编码。"""
    s = s.replace("+", " ")
    parts = s.split("%")
    if len(parts) == 1:
        return s
    res = parts[0]
    for item in parts[1:]:
        try:
            res += chr(int(item[:2], 16)) + item[2:]
        except ValueError:
            res += "%" + item
    return res

def start_config_server(current_config, display_module, check_button_func):
    """
    启动 AP 模式和 Web 服务器 (非阻塞，以检查重置按钮)
    依赖注入：display_module, check_button_func
    """

    display_module.oled_show_config_mode()
    
    # 启动 AP
    network.WLAN(network.STA_IF).active(False)
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    try:
        ap_config = (config.AP_IP, config.AP_NETMASK, config.AP_IP, config.AP_IP)
        ap.ifconfig(ap_config)
    except Exception as e:
        print(f"!!!!! 错误: 设置 AP 静态 IP 失败: {e} !!!!!")
        
    ap.config(essid=config.AP_SSID, authmode=network.AUTH_OPEN)
    
    print("\n=====================================")
    print(f"DEBUG: 配置热点已启动: {config.AP_SSID}")
    print(f"DEBUG: 请连接此 WiFi 并在浏览器中访问 http://{config.AP_IP}")
    print("=====================================\n")

    # 启动 Socket
    addr = usocket.getaddrinfo("0.0.0.0", 80)[0][-1]
    s = usocket.socket()
    s.setsockopt(usocket.SOL_SOCKET, usocket.SO_REUSEADDR, 1)
    s.settimeout(0.5)  # 非阻塞
    s.bind(addr)
    s.listen(1)
    
    if config.DEBUG: print("DEBUG: 配置网页服务器正在监听 :80...")

    cl = None

    while True:
        check_button_func(display_module.oled_show_message) 

        try:
            cl, addr = s.accept() # 0.5秒超时
            if config.DEBUG: print(f"DEBUG: 客户端连接来自: {addr}")
            cl.settimeout(0.5)
            
            try:
                request = cl.recv(1024)
                request = request.decode("utf-8")
            except Exception:
                cl.close()
                cl = None
                continue

            def http_response(cl_socket, status_code, content_type, content):
                content_bytes = content.encode("utf-8")
                if "text/html" in content_type and "charset=" not in content_type:
                    content_type += "; charset=utf-8"
                
                try:
                    cl_socket.send(f"HTTP/1.1 {status_code}\r\n")
                    cl_socket.send(f"Content-Type: {content_type}\r\n")
                    cl_socket.send("Connection: close\r\n\r\n")
                    cl_socket.sendall(content_bytes)
                except Exception as e:
                    if config.DEBUG: print(f"DEBUG: HTTP 响应发送失败: {e}")

            is_save_request = request.find("GET /save?") == 0
            is_root_request = request.find("GET / HTTP") == 0

            if is_save_request:
                if config.DEBUG: print("DEBUG: 收到 /save 请求...")
                try:
                    params_str = request.split("?")[1].split(" ")[0]
                    params = {}
                    for pair in params_str.split("&"):
                        k, v = pair.split("=", 1)
                        params[k] = _unquote_plus(v)
                    
                    if config.DEBUG: print(f"DEBUG: 解析到的参数: {params}")

                    # (V38) 保存逻辑
                    new_config = config.DEFAULT_CONFIG.copy() # 从默认值开始
                    new_config.update({
                        "wifi_ssid": params.get("ssid", ""),
                        "wifi_pass": params.get("pass", ""),
                        "nfc_mqtt_topic_base": params.get(
                            "nfc_mqtt_topic_base", config.DEFAULT_CONFIG["nfc_mqtt_topic_base"]
                        ),
                        "mqtt_broker": params.get("mqtt_broker", ""),
                        "mqtt_port": params.get("mqtt_port", config.DEFAULT_CONFIG["mqtt_port"]),
                        "mqtt_user": params.get("mqtt_user", ""),
                        "mqtt_pass": params.get("mqtt_pass", ""),
                        "mqtt_client_id": params.get(
                            "mqtt_client_id", config.DEFAULT_CONFIG["mqtt_client_id"]
                        ),
                        "mqtt_topic_temp": params.get(
                            "mqtt_topic_temp", config.DEFAULT_CONFIG["mqtt_topic_temp"]
                        ),
                        "mqtt_topic_humidity": params.get(
                            "mqtt_topic_humidity", config.DEFAULT_CONFIG["mqtt_topic_humidity"]
                        ),
                    })
                    try:
                        new_config["mqtt_port"] = int(params.get("mqtt_port", config.DEFAULT_CONFIG["mqtt_port"]))
                    except ValueError:
                        new_config["mqtt_port"] = config.DEFAULT_CONFIG["mqtt_port"]
                    
                    config.save_config(new_config) # 使用 config 模块的函数

                    html_success = """
                    <html><head><title>保存成功</title><meta charset="UTF-8"><meta name=viewport content="width=device-width,initial-scale=1"></head>
                    <body style="font-family:sans-serif;text-align:center;padding:20px;">
                        <h1>配置已保存</h1>
                        <p>设备将自动重启并尝试连接到新的 WiFi。</p>
                    </body></html>
                    """
                    http_response(cl, "200 OK", "text/html", html_success)
                    
                    display_module.oled_show_message("配置已保存", "3秒后重启...")
                    if config.DEBUG: print("DEBUG: 3秒后重启...")
                    time.sleep(3)
                    machine.reset()

                except Exception as e:
                    print(f"!!!!! 错误: 解析 /save 请求失败: {e} !!!!!")
                    http_response(
                        cl,
                        "500 Internal Error",
                        "text/plain",
                        "Server Error during save.",
                    )

            elif is_root_request:
                if config.DEBUG: print("DEBUG: 收到 / (root) 请求...")

                html_form = f"""
                <html>
                <head>
                    <title>AMS Sensor 配置</title>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <style>
                        body {{ font-family: sans-serif; margin: 20px; background: #f4f4f4; }}
                        h1 {{ text-align: center; color: #333; }}
                        form {{ max-width: 500px; margin: 0 auto; padding: 20px; background: #fff; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                        div {{ margin-bottom: 15px; }}
                        label {{ display: block; margin-bottom: 5px; font-weight: bold; color: #555; }}
                        input[type="text"], input[type="password"] {{ width: -webkit-fill-available; padding: 8px; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; }}
                        button {{ width: 100%; padding: 10px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }}
                        button:hover {{ background: #0056b3; }}
                        h3 {{ border-bottom: 1px solid #eee; padding-bottom: 5px; }}
                        details {{ border: 1px solid #eee; border-radius: 4px; padding: 10px; margin-top: 10px; }}
                        summary {{ font-weight: bold; cursor: pointer; color: #007bff; }}
                    </style>
                </head>
                <body>
                    <h1>ESP32 AMS Sensor 配置</h1>
                    <form action="/save" method="get">
                        <h3>WiFi 设置 (必填)</h3>
                        <div><label for="ssid">WiFi 名称 (SSID):</label><input type="text" id="ssid" name="ssid" value="{current_config.get('wifi_ssid', '')}" required></div>
                        <div><label for="pass">WiFi 密码:</label><input type="password" id="pass" name="pass" value="{current_config.get('wifi_pass', '')}"></div>
                        <hr>
                        
                        <h3>MQTT 设置 (必填)</h3>
                        <div><label for="mqtt_broker">MQTT Broker IP / 地址:</label><input type="text" id="mqtt_broker" name="mqtt_broker" value="{current_config.get('mqtt_broker', '')}" required></div>
                        <div><label for="mqtt_port">MQTT 端口:</label><input type="text" id="mqtt_port" name="mqtt_port" value="{current_config.get('mqtt_port', 1883)}"></div>
                        <div><label for="mqtt_user">MQTT 用户名 (可选):</label><input type="text" id="mqtt_user" name="mqtt_user" value="{current_config.get('mqtt_user', '')}"></div>
                        <div><label for="mqtt_pass">MQTT 密码 (可选):</label><input type="password" id="mqtt_pass" name="mqtt_pass" value="{current_config.get('mqtt_pass', '')}"></div>
                        
                        <details>
                            <summary>高级选项 (Client ID 和 Topics)</summary>
                            <div><label for="mqtt_client_id">MQTT 客户端 ID:</label><input type="text" id="mqtt_client_id" name="mqtt_client_id" value="{current_config.get('mqtt_client_id', 'ams-nfc-sensor')}"></div>
                            
                            <h4>Topic 设置 (温湿度)</h4>
                            <div><label for="mqtt_topic_temp">温度 Topic:</label><input type="text" id="mqtt_topic_temp" name="mqtt_topic_temp" value="{current_config.get('mqtt_topic_temp', 'ams_sensor/temperature')}"></div>
                            <div><label for="mqtt_topic_humidity">湿度 Topic:</label><input type="text" id="mqtt_topic_humidity" name="mqtt_topic_humidity" value="{current_config.get('mqtt_topic_humidity', 'ams_sensor/humidity')}"></div>

                            <h4>Topic 设置 (NFC/料盘)</h4>
                            <div><label for="nfc_mqtt_topic_base">NFC Topic (Base):</label><input type="text" id="nfc_mqtt_topic_base" name="nfc_mqtt_topic_base" value="{current_config.get('nfc_mqtt_topic_base', 'ams_sensor/nfc')}"></div>
                        </details>

                        <br>
                        <button type="submit">保存并重启</button>
                    </form>
                    </body>
                </html>
                """
                http_response(cl, "200 OK", "text/html", html_form)

            else:
                if config.DEBUG: print("DEBUG: 收到 404 (Not Found) 请求...")
                http_response(
                    cl,
                    "404 Not Found",
                    "text/plain",
                    f"Not Found. Try http://{config.AP_IP}",
                )

        except OSError as e:
            pass
        except Exception as e:
            print(f"!!!!! 致命错误: Web 服务器主循环: {e} !!!!!")

        finally:
            if cl:
                cl.close()
                cl = None