import pyaudiowpatch as pyaudio
import numpy as np
import threading
from queue import Queue
from config import Config


class AudioCapture(threading.Thread):
    def __init__(self, audio_queue: Queue):
        super().__init__()
        self.audio_queue = audio_queue
        self.running = False
        self.p = pyaudio.PyAudio()
        self.device_index = None

    def _find_loopback_device(self):
        """寻找 Windows 的系统内录设备 (Loopback)"""
        print("[Audio] 正在扫描音频设备...")
        try:
            wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = self.p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])

            print(f"[Audio] 默认输出设备: {default_speakers['name']}")

            if not default_speakers["isLoopbackDevice"]:
                for loopback in self.p.get_loopback_device_info_generator():
                    if default_speakers["name"] in loopback["name"]:
                        return loopback["index"]
            else:
                return default_speakers["index"]
        except Exception as e:
            print(f"[Audio] 设备查找出错: {e}")
        return None

    def run(self):
        self.device_index = self._find_loopback_device()
        if self.device_index is None:
            print("[Audio] ❌ 错误: 未找到系统内录设备。")
            return

        # --- 关键修复：获取设备真实的采样率和通道数 ---
        try:
            dev_info = self.p.get_device_info_by_index(self.device_index)
            # 调试日志：打印设备完整信息
            print(f"[Audio] 🔍 设备完整信息:")
            print(f"    - 索引: {self.device_index}")
            print(f"    - 名称: {dev_info.get('name', 'N/A')}")
            print(f"    - 最大输入通道: {dev_info.get('maxInputChannels', 'N/A')}")
            print(f"    - 最大输出通道: {dev_info.get('maxOutputChannels', 'N/A')}")
            print(f"    - 默认采样率: {dev_info.get('defaultSampleRate', 'N/A')}")
            print(f"    - isLoopbackDevice: {dev_info.get('isLoopbackDevice', 'N/A')}")
            
            # 大多数 Windows 设备是 48000 或 44100
            native_rate = int(dev_info["defaultSampleRate"])
            # 获取设备原生通道数（loopback 设备通常是立体声）
            native_channels = int(dev_info.get("maxInputChannels", 2))
            if native_channels == 0:
                native_channels = 2  # loopback 设备可能报告 maxInputChannels=0，使用默认立体声
            
            print(f"[Audio] ✅ 设备原生采样率: {native_rate}Hz, 通道数: {native_channels}")
            print(f"[Audio] ℹ️ Whisper 需要 16000Hz 单声道，将自动转换")
        except Exception as e:
            print(f"[Audio] 获取设备信息失败: {e}")
            native_rate = 48000
            native_channels = 2

        self.running = True

        stream = None
        try:
            # 使用原生采样率和通道数打开流，避免 -9996/-9997 错误
            stream = self.p.open(
                format=pyaudio.paFloat32,
                channels=native_channels,  # 使用设备原生通道数（通常是2）
                rate=native_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=int(native_rate * 0.1)  # 100ms 缓冲区
            )

            print(f"[Audio] ✅ 开始捕获系统音频 (采样率={native_rate}Hz, 通道={native_channels})")

            while self.running:
                # 1. 读取原生数据 (比如 48000Hz, 立体声)
                # 阻塞读取防止 CPU 空转
                frames_to_read = int(native_rate * 0.5)  # 500ms 的帧数
                data = stream.read(frames_to_read, exception_on_overflow=False)
                native_np = np.frombuffer(data, dtype=np.float32)

                # 2. 如果是立体声，转换为单声道（取两个通道的平均值）
                if native_channels == 2:
                    # 立体声数据交错存储: [L0, R0, L1, R1, ...]
                    # 重塑为 (N, 2) 然后取平均
                    native_np = native_np.reshape(-1, 2).mean(axis=1).astype(np.float32)

                # 3. 如果原生频率不是 16000，则需要重采样
                if native_rate != Config.SAMPLE_RATE:
                    # 计算目标长度
                    target_len = int(len(native_np) * Config.SAMPLE_RATE / native_rate)
                    # 使用 numpy 进行线性插值重采样 (简单且无需额外依赖)
                    audio_np = np.interp(
                        np.linspace(0.0, 1.0, target_len, endpoint=False),  # 目标 X 轴
                        np.linspace(0.0, 1.0, len(native_np), endpoint=False),  # 源 X 轴
                        native_np  # 源数据
                    ).astype(np.float32)
                else:
                    audio_np = native_np.copy()

                # 4. 放入队列
                self.audio_queue.put(audio_np)

        except Exception as e:
            print(f"[Audio] 捕获异常: {e}")
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()
            self.p.terminate()
            print("[Audio] 服务已停止")

    def stop(self):
        self.running = False