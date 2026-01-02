# 串口转发工具

用于AI和实际串口设备之间的通信工具。支持波特率最高2M，8N1配置（8数据位，无校验，1停止位）。

> **为什么不做成MCP？** 因为太麻烦了，还需要配置安装。直接把源码git下来，直接就可以使用。  
> **主要用途：** 方便调试Linux开发板，让AI通过串口控制整个开发板，提高效率。

## 功能特性

- ✅ 支持波特率最高 2,000,000 (2M)
- ✅ 默认8N1 配置，也可以用其他的配置
- ✅ 异步接收数据，实时获取设备返回
- ✅ 支持文本、十六进制、字节数组多种数据格式
- ✅ 命令行接口，方便AI调用
- ✅ 自动记录通信日志

## 快速开始

### 1. 获取项目并安装依赖

```bash
git clone https://github.com/CHTUZKI/Ai_SerialPort_Tool.git

pip install -r requirements.txt
```

### 2. 使用AI IDE打开项目

使用 **VSCode**、**Windsurf** 或 **Trea** 等支持AI的IDE打开项目目录。

### 3. 告诉AI你的设备信息

在AI IDE中，直接告诉AI你的串口设备信息，例如：

```
我当前设备的串口号是COM4，波特率1.5M，8N1配置。
你给我用serial_forwarder用ifconfig看一下我Linux开发板的ip地址。
```

AI会自动执行：
```bash
python serial_forwarder.py --port COM4 --baudrate 1500000 --send "ifconfig\r\n" --receive --output-format json
```

## 命令行使用

### 基本用法

```bash
# 列出可用串口
python serial_forwarder.py --list

# 发送命令并接收回复
python serial_forwarder.py --port COM4 --baudrate 1500000 --send "ifconfig\r\n" --receive

# 发送十六进制数据
python serial_forwarder.py --port COM3 --send-hex "41540D0A" --receive

# 仅接收数据
python serial_forwarder.py --port COM3 --receive --receive-timeout 2.0

# 交互模式（调试用）
python serial_forwarder.py --port COM3 --baudrate 115200 --interactive

# JSON输出格式（方便AI解析）
python serial_forwarder.py --port COM3 --send "AT\r\n" --receive --output-format json
```

### 主要参数

- `--port, -p`: 串口名称（必需，除非使用 --list）
- `--baudrate, -b`: 波特率（默认115200，最高支持2000000）
- `--send, -s`: 发送文本数据
- `--send-hex`: 发送十六进制数据
- `--receive, -r`: 接收数据
- `--receive-timeout`: 接收超时时间（秒，默认1.0）
- `--wait-time`: 发送后等待接收的时间（秒，默认0.1）
- `--output-format`: 输出格式（text/hex/json，默认text）
- `--interactive, -i`: 交互模式

## 通信日志

程序会自动记录所有串口通信数据到 `serial_communication.log` 文件中：

```
[01:16:43.593] [--->] ifconfig
[01:16:43.650] [<---] eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
[01:16:43.651] [<---]         inet 192.168.1.100  netmask 255.255.255.0
```

- `--->` 表示发送的数据
- `<---` 表示接收的数据
- 时间戳格式：`时:分:秒.毫秒`

## 注意事项

1. **串口名称：** Windows用 `COM1/COM2`，Linux用 `/dev/ttyUSB0`，macOS用 `/dev/cu.usbserial-*`
2. **高波特率：** 需要硬件支持（如FT232H、CH340等芯片）
3. **命令结束符：** Linux命令通常需要 `\r\n` 或 `\n`
4. **超时调整：** 使用 `--wait-time` 和 `--receive-timeout` 参数调整等待时间

