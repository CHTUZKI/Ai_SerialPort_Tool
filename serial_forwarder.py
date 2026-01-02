#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
串口转发工具
用于AI和实际串口设备之间的通信
支持波特率最高2M，8N1配置
"""

import serial
import serial.tools.list_ports
import threading
import time
import sys
import json
import argparse
import os
from datetime import datetime
from queue import Queue
from typing import Optional, List


class SerialForwarder:
    """串口转发器类"""
    
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 1.0):
        """
        初始化串口转发器
        
        Args:
            port: 串口名称，如 'COM3' 或 '/dev/ttyUSB0'
            baudrate: 波特率，支持最高2000000 (2M)
            timeout: 读取超时时间（秒）
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn: Optional[serial.Serial] = None
        self.receive_queue = Queue()
        self.is_running = False
        self.receive_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        
        # 初始化日志系统
        self.log_file = "serial_communication.log"
        self._init_log()
        
    def _init_log(self):
        """初始化日志文件，每次运行都覆盖旧数据"""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write(f"# 串口通信日志 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 串口: {self.port}, 波特率: {self.baudrate}\n")
                f.write("# 格式: [时间戳] [方向(--->/<---)] 数据内容\n")
                f.write("-" * 60 + "\n")
        except Exception as e:
            print(f"初始化日志文件失败: {e}", file=sys.stderr)
    
    def _write_log(self, direction: str, data: bytes):
        """写入日志"""
        try:
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]

            # 转换方向标签为箭头
            direction_symbol = "--->" if direction == "SEND" else "<---" if direction == "RECV" else direction
            
            # 尝试解码为文本，如果失败则显示十六进制
            try:
                text_data = data.decode('utf-8')
                # 对于可打印字符，直接显示原始内容
                if all(ord(c) < 128 and (c.isprintable() or c in '\r\n\t') for c in text_data):
                    # 将多行内容拆分并过滤空行，避免日志出现空行
                    lines = text_data.replace('\r\n', '\n').replace('\r', '\n').split('\n')
                    non_empty_lines = [line for line in lines if line.strip()]
                    if not non_empty_lines:
                        return

                    log_line = "".join(
                        f"[{timestamp}] [{direction_symbol}] {line.rstrip()}\n" for line in non_empty_lines
                    )
                else:
                    # 包含不可打印字符，显示十六进制
                    log_line = f"[{timestamp}] [{direction_symbol}] HEX: {data.hex()}\n"
            except UnicodeDecodeError:
                # 解码失败，显示十六进制
                log_line = f"[{timestamp}] [{direction_symbol}] HEX: {data.hex()}\n"
            
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_line)
        except Exception as e:
            print(f"写入日志失败: {e}", file=sys.stderr)
        
    def connect(self) -> bool:
        """
        连接串口
        
        Returns:
            bool: 连接是否成功
        """
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,      # 8数据位
                parity=serial.PARITY_NONE,      # 无校验
                stopbits=serial.STOPBITS_ONE,   # 1停止位
                timeout=self.timeout
            )
            
            # 清空缓冲区
            time.sleep(0.1)  # 等待串口稳定
            self.serial_conn.reset_input_buffer()
            self.serial_conn.reset_output_buffer()
            
            # 清空接收队列
            while not self.receive_queue.empty():
                try:
                    self.receive_queue.get_nowait()
                except:
                    break
            
            self.is_running = True
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
            return True
        except Exception as e:
            print(f"连接串口失败: {e}", file=sys.stderr)
            return False
    
    def disconnect(self):
        """断开串口连接"""
        self.is_running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=2.0)
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
    
    def _receive_loop(self):
        """接收数据循环（后台线程）"""
        while self.is_running and self.serial_conn and self.serial_conn.is_open:
            try:
                # 检查是否有数据可读
                if self.serial_conn.in_waiting > 0:
                    # 读取所有可用数据
                    data = self.serial_conn.read(self.serial_conn.in_waiting)
                    if data:
                        # 将数据放入队列
                        self.receive_queue.put(data)
                        # 记录接收日志
                        self._write_log("RECV", data)
                else:
                    # 没有数据时短暂休眠，避免CPU占用过高
                    time.sleep(0.01)
            except Exception as e:
                if self.is_running:
                    print(f"接收数据错误: {e}", file=sys.stderr)
                break
    
    def send(self, data: bytes) -> bool:
        """
        发送数据到串口
        
        Args:
            data: 要发送的字节数据
            
        Returns:
            bool: 发送是否成功
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            print("串口未连接", file=sys.stderr)
            return False
        
        try:
            with self.lock:
                self.serial_conn.write(data)
                self.serial_conn.flush()
                # 记录发送日志
                self._write_log("SEND", data)
            return True
        except Exception as e:
            print(f"发送数据失败: {e}", file=sys.stderr)
            return False
    
    def receive(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """
        接收数据（从队列中获取）
        
        Args:
            timeout: 超时时间（秒），None表示不超时
            
        Returns:
            bytes: 接收到的数据，超时返回None
        """
        try:
            if timeout is None:
                return self.receive_queue.get(block=True)
            else:
                return self.receive_queue.get(block=True, timeout=timeout)
        except:
            return None
    
    def receive_all(self, timeout: float = 1.0) -> bytes:
        """
        接收所有可用数据
        
        Args:
            timeout: 等待超时时间（秒）
            
        Returns:
            bytes: 所有接收到的数据
        """
        result = b''
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # 尝试从队列获取数据
                data = self.receive_queue.get(timeout=0.1)
                if data:
                    result += data
                    # 如果获取到数据，继续等待更多数据
                    start_time = time.time()  # 重置超时时间
            except:
                # 队列为空，检查是否还有更多数据会来
                if len(result) > 0:
                    # 已经有数据，再等待一小段时间看是否还有更多
                    time.sleep(0.1)
                    break
                time.sleep(0.01)
        
        return result
    
    def is_connected(self) -> bool:
        """检查串口是否已连接"""
        return self.serial_conn is not None and self.serial_conn.is_open


def list_ports():
    """列出所有可用的串口"""
    ports = serial.tools.list_ports.comports()
    return [{"port": p.device, "description": p.description} for p in ports]


def main():
    """主函数 - 命令行接口"""
    parser = argparse.ArgumentParser(description='串口转发工具 - AI与串口设备通信')
    parser.add_argument('--port', '-p', type=str, help='串口名称，如 COM3 或 /dev/ttyUSB0')
    parser.add_argument('--baudrate', '-b', type=int, default=115200, 
                       help='波特率（默认115200，最高支持2000000）')
    parser.add_argument('--list', '-l', action='store_true', help='列出所有可用串口')
    parser.add_argument('--send', '-s', type=str, help='发送数据（字符串）')
    parser.add_argument('--send-hex', type=str, help='发送数据（十六进制字符串，如 FF00AA）')
    parser.add_argument('--send-bytes', type=str, help='发送数据（字节数组，如 [255,0,170]）')
    parser.add_argument('--receive', '-r', action='store_true', help='接收数据')
    parser.add_argument('--receive-timeout', type=float, default=1.0, 
                       help='接收超时时间（秒，默认1.0）')
    parser.add_argument('--wait-time', type=float, default=0.1,
                       help='发送后等待接收的时间（秒，默认0.1）')
    parser.add_argument('--output-format', choices=['text', 'hex', 'json'], default='text',
                       help='输出格式（默认text）')
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='交互模式，持续监听和发送')
    
    args = parser.parse_args()
    
    # 列出串口
    if args.list:
        ports = list_ports()
        if ports:
            print("可用串口:")
            for p in ports:
                print(f"  {p['port']}: {p['description']}")
        else:
            print("未找到可用串口")
        return
    
    # 需要串口参数的操作
    if not args.port:
        print("错误: 请指定串口（使用 --port 或 -p）", file=sys.stderr)
        print("使用 --list 查看可用串口", file=sys.stderr)
        sys.exit(1)
    
    # 创建转发器
    forwarder = SerialForwarder(args.port, args.baudrate)
    
    try:
        # 连接串口
        if not forwarder.connect():
            sys.exit(1)
        
        # 交互模式
        if args.interactive:
            print(f"已连接到 {args.port}，波特率 {args.baudrate}")
            print("输入命令:")
            print("  send <数据> - 发送文本数据")
            print("  sendhex <十六进制> - 发送十六进制数据")
            print("  receive - 接收数据")
            print("  quit - 退出")
            print()
            
            while True:
                try:
                    cmd = input("> ").strip()
                    if not cmd:
                        continue
                    
                    if cmd == 'quit' or cmd == 'exit':
                        break
                    elif cmd == 'receive':
                        data = forwarder.receive_all(timeout=1.0)
                        if data:
                            # 尝试多种编码方式显示
                            try:
                                text = data.decode('utf-8')
                                print(f"接收 (UTF-8): {text}")
                            except:
                                try:
                                    text = data.decode('gbk')
                                    print(f"接收 (GBK): {text}")
                                except:
                                    print(f"接收 (HEX): {data.hex()}")
                        else:
                            print("未接收到数据")
                    elif cmd.startswith('send '):
                        text = cmd[5:]
                        if forwarder.send(text.encode('utf-8')):
                            print("发送成功")
                            time.sleep(0.5)
                            data = forwarder.receive_all(timeout=2.0)
                            if data:
                                # 尝试多种编码方式显示
                                try:
                                    decoded_text = data.decode('utf-8')
                                    print(f"接收 (UTF-8): {decoded_text}")
                                except:
                                    try:
                                        decoded_text = data.decode('gbk')
                                        print(f"接收 (GBK): {decoded_text}")
                                    except:
                                        print(f"接收 (HEX): {data.hex()}")
                    elif cmd.startswith('sendhex '):
                        hex_str = cmd[8:].replace(' ', '')
                        try:
                            data = bytes.fromhex(hex_str)
                            if forwarder.send(data):
                                print("发送成功")
                                time.sleep(0.1)
                                data = forwarder.receive_all(timeout=0.5)
                                if data:
                                    print(f"接收: {data.hex()}")
                        except ValueError as e:
                            print(f"错误: 无效的十六进制字符串 - {e}")
                    else:
                        print("未知命令")
                except KeyboardInterrupt:
                    break
                except EOFError:
                    break
        else:
            # 单次操作模式
            result = {}
            
            # 发送数据
            if args.send:
                # 处理换行符
                send_data = args.send.replace('\\r', '\r').replace('\\n', '\n')
                success = forwarder.send(send_data.encode('utf-8'))
                result['send_success'] = success
                if success:
                    time.sleep(args.wait_time)
            
            if args.send_hex:
                try:
                    data = bytes.fromhex(args.send_hex.replace(' ', ''))
                    success = forwarder.send(data)
                    result['send_success'] = success
                    if success:
                        time.sleep(args.wait_time)
                except ValueError as e:
                    result['error'] = f"无效的十六进制字符串: {e}"
            
            if args.send_bytes:
                try:
                    byte_list = json.loads(args.send_bytes)
                    data = bytes(byte_list)
                    success = forwarder.send(data)
                    result['send_success'] = success
                    if success:
                        time.sleep(args.wait_time)
                except Exception as e:
                    result['error'] = f"无效的字节数组: {e}"
            
            # 接收数据
            if args.receive or args.send or args.send_hex or args.send_bytes:
                # 等待一段时间让数据到达
                if args.send or args.send_hex or args.send_bytes:
                    time.sleep(args.wait_time)
                
                data = forwarder.receive_all(timeout=args.receive_timeout)
                if data:
                    if args.output_format == 'hex':
                        result['received'] = data.hex()
                    elif args.output_format == 'json':
                        result['received'] = list(data)
                        try:
                            result['received_text'] = data.decode('utf-8')
                        except:
                            result['received_text'] = data.decode('utf-8', errors='replace')
                    else:
                        try:
                            result['received'] = data.decode('utf-8')
                        except:
                            result['received'] = data.decode('utf-8', errors='replace')
                else:
                    result['received'] = None
            
            # 输出结果
            if args.output_format == 'json':
                print(json.dumps(result, ensure_ascii=False))
            else:
                if 'received' in result:
                    if result['received']:
                        print(result['received'])
                    else:
                        print("未接收到数据", file=sys.stderr)
    
    finally:
        forwarder.disconnect()


if __name__ == '__main__':
    main()

