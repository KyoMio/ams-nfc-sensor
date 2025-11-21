import time
import ubinascii
import micropython
import config

# --- 导入依赖库 ---
try:
    import ndef
    from mfrc522 import MFRC522
    mfrc522 = True
except ImportError as e:
    print(f"!!!!! 致命错误: 缺少 MFRC522 或 NDEF 库: {e} !!!!!")
    mfrc522 = None
    ndef = None

def init_readers():
    """
    根据 config.py 中的定义初始化所有 MFRC522 读卡器。
    """
    if mfrc522 is None:
        return []
        
    readers = []
    spi_pins = config.READER_SPI_SHARED
    
    try:
        for i, reader_pins in enumerate(config.READER_PINS):
            if config.DEBUG:
                print(f"DEBUG: 初始化读卡器 {i+1} (CS={reader_pins['cs']}, RST={reader_pins['rst']})...")
            
            readers.append(
                MFRC522(
                    sck=spi_pins['sck'],
                    mosi=spi_pins['mosi'],
                    miso=spi_pins['miso'],
                    rst=reader_pins['rst'],
                    cs=reader_pins['cs']
                )
            )
        if config.DEBUG:
            print(f"DEBUG: {len(readers)}个 MFRC522 读卡器已初始化。")
        return readers
    except Exception as e:
        print(f"!!!!! 致命错误: MFRC522 初始化失败: {e} !!!!!")
        return []


@micropython.native  # (V39) 优化: 编译为本地字节码
def parse_ndef_message(raw_data):
    """
    从原始页数据中解析 NDEF 消息。
    """
    if ndef is None: return None
    
    if config.DEBUG: print("  [.] 正在解析 NDEF 数据...")
    try:
        offset = 0
        while offset < len(raw_data):
            tlv_type = raw_data[offset]
            offset += 1
            if offset >= len(raw_data):
                if config.DEBUG: print(f"  [!] TLV 解析错误: 在读取 T:0x{tlv_type:X} 后数据意外结束。")
                break
            tlv_length = raw_data[offset]
            offset += 1
            if tlv_length == 0xFF:
                if (offset + 2) > len(raw_data):
                    if config.DEBUG: print(f"  [!] TLV 解析错误: 3字节长度字段数据不足。")
                    break
                tlv_length = (raw_data[offset] << 8) | raw_data[offset + 1]
                offset += 2
            if tlv_type == 0x03:
                if config.DEBUG: print(f"  [+] 找到 NDEF Message TLV (Type 0x03)，长度: {tlv_length} 字节")
                msg_start_index = offset
                msg_end_index = msg_start_index + tlv_length
                if msg_end_index > len(raw_data):
                    if config.DEBUG: print(f"  [!] TLV 解析错误: NDEF 消息长度 ({tlv_length}) 超出数据范围。")
                    break
                ndef_message_bytes = raw_data[msg_start_index:msg_end_index]
                
                for record in ndef.message_decoder(ndef_message_bytes, errors="strict"):
                    if config.DEBUG: print(f"    - 记录类型: {record.type}")
                    if isinstance(record, ndef.text.TextRecord):
                        if config.DEBUG: print(f"    >>> 找到文本: {record.text}")
                        return record.text
                    elif isinstance(record, ndef.microuri.MicroUri):
                        if config.DEBUG: print(f"    >>> 找到 URI: {record.uri}")
                return None
            elif tlv_type == 0x00:
                if config.DEBUG: print("  [.] 跳过 Null TLV (0x00)")
                continue
            elif tlv_type == 0xFE:
                if config.DEBUG: print("  [.] 遇到 Terminator TLV (0xFE)，停止解析。")
                break
            else:
                if config.DEBUG: print(f"  [.] 跳过未知 TLV (Type 0x{tlv_type:X}), 长度: {tlv_length}")
                offset += tlv_length
                if offset > len(raw_data):
                    if config.DEBUG: print(f"  [!] TLV 解析错误: TLV 0x{tlv_type:X} 的值超出了数据范围。")
                    break
        if config.DEBUG: print("  [!] 遍历了所有 TLV，未找到 NDEF 消息 (Type 0x03)。")
    except Exception as e:
        print(f"  [!] 解析 NDEF 失败 (错误类型: {type(e).__name__}): {e}")
    return None


def read_ultralight_ndef(rdr):
    """
    读取 NTAG/Ultralight 标签的 NDEF 数据。
    """
    if config.DEBUG: print("  [.] 正在读取 NTAG/Ultralight NDEF...")
    all_data = bytearray()
    pages_to_read = []
    for i in range(11):
        pages_to_read.append(0x04 + (i * 4)) 
        
    for page_addr in pages_to_read:
        data = None
        for retry in range(3):
            data = rdr.read(page_addr)
            if data:
                break
            else:
                if config.DEBUG: print(f"    - 读取块 {page_addr} 失败 (尝试 {retry+1}/3)")
                time.sleep_ms(10)
        if data:
            all_data.extend(data)
        else:
            print(f"  [!] 读取 Page {page_addr} 彻底失败 (已重试 3 次)。")
            break # 停止读取
            
    if not all_data:
        if config.DEBUG: print("  [!] 未能从标签读取任何数据。")
        return None
        
    if config.DEBUG: print(f"  [+] 总共读取 {len(all_data)} 字节的原始数据。")
    
    if len(all_data) > 0:
        return parse_ndef_message(all_data)
    else:
        return None


def read_tag_text(reader_obj):
    """
    尝试从 MFRC522 读卡器实例中读取单个 NDEF 文本。
    """
    detected_text = None
    (stat, tag_type) = reader_obj.request(reader_obj.REQIDL)
    if stat != reader_obj.OK:
        return None
        
    (stat, raw_uid) = reader_obj.anticoll()
    if stat != reader_obj.OK:
        return None
        
    if reader_obj.select_tag(raw_uid) == reader_obj.OK:
        detected_text = read_ultralight_ndef(reader_obj)
        if detected_text:
            return detected_text.strip()
            
    return None