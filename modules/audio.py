import pyaudiowpatch as pyaudio
import numpy as np
import threading
import time
import wave
from queue import Queue
from config import Config


class AudioCapture(threading.Thread):
    def __init__(self, audio_queue: Queue):
        super().__init__()
        self.audio_queue = audio_queue
        self.running = False
        self.p = pyaudio.PyAudio()
        self.device_info = None

    def _find_loopback_device(self):
        """使用 PyAudioWPatch 官方 API 获取 WASAPI Loopback 设备"""
        print("[Audio] 正在扫描音频设备...")
        
        try:
            # 使用官方推荐的 API 获取默认 WASAPI loopback 设备
            self.device_info = self.p.get_default_wasapi_loopback()
            print(f"[Audio] ✅ 找到默认 WASAPI Loopback: {self.device_info['name']}")
            return self.device_info
        except Exception as e:
            print(f"[Audio] ⚠️ get_default_wasapi_loopback 失败: {e}")
        
        # 备选方案：遍历所有 loopback 设备
        try:
            print("[Audio] 尝试遍历 loopback 设备...")
            for loopback in self.p.get_loopback_device_info_generator():
                print(f"[Audio]   发现: {loopback['name']}")
                self.device_info = loopback
                return loopback
        except Exception as e:
            print(f"[Audio] ⚠️ 遍历 loopback 设备失败: {e}")
        
        return None

    def run(self):
        device = self._find_loopback_device()
        if device is None:
            print("[Audio] ❌ 错误: 未找到系统内录设备。")
            print("[Audio] 💡 提示: 请检查音频设备或尝试重启 Windows Audio 服务")
            return

        # 打印设备详细信息
        print(f"[Audio] 🔍 设备完整信息:")
        print(f"    - 索引: {device['index']}")
        print(f"    - 名称: {device['name']}")
        print(f"    - 最大输入通道: {device['maxInputChannels']}")
        print(f"    - 最大输出通道: {device['maxOutputChannels']}")
        print(f"    - 默认采样率: {device['defaultSampleRate']}")
        print(f"    - isLoopbackDevice: {device.get('isLoopbackDevice', 'N/A')}")

        # 使用设备的原生参数
        native_rate = int(device["defaultSampleRate"])
        native_channels = device["maxInputChannels"]
        
        # loopback 设备的 maxInputChannels 通常是正确的
        if native_channels == 0:
            native_channels = 2
            print(f"[Audio] ⚠️ maxInputChannels 为 0，使用默认值 2")

        print(f"[Audio] ✅ 设备原生采样率: {native_rate}Hz, 通道数: {native_channels}")
        print(f"[Audio] ℹ️ Whisper 需要 16000Hz 单声道，将自动转换")

        self.running = True
        stream = None
        
        try:
            # 根据官方示例，使用阻塞模式但减小缓冲区大小
            CHUNK = int(native_rate * 0.1)  # 100ms
            
            stream = self.p.open(
                format=pyaudio.paInt16,  # 使用 Int16 格式，更通用
                channels=native_channels,
                rate=native_rate,
                input=True,
                input_device_index=device["index"],
                frames_per_buffer=CHUNK
            )

            print(f"[Audio] ✅ 开始捕获系统音频 (采样率={native_rate}Hz, 通道={native_channels}, chunk={CHUNK})")
            
            read_count = 0
            last_debug_time = time.time()

            while self.running:
                try:
                    # 读取音频数据
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    read_count += 1
                    
                    # 前几次读取打印调试信息
                    if read_count <= 3:
                        print(f"[Audio] ✅ 第 {read_count} 次读取成功，数据长度: {len(data)} bytes")
                    
                    # 转换为 numpy 数组 (Int16 -> Float32)
                    native_np = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0

                    # 立体声转单声道
                    if native_channels == 2:
                        native_np = native_np.reshape(-1, 2).mean(axis=1).astype(np.float32)

                    # 重采样到 16000Hz
                    if native_rate != Config.SAMPLE_RATE:
                        target_len = int(len(native_np) * Config.SAMPLE_RATE / native_rate)
                        audio_np = np.interp(
                            np.linspace(0.0, 1.0, target_len, endpoint=False),
                            np.linspace(0.0, 1.0, len(native_np), endpoint=False),
                            native_np
                        ).astype(np.float32)
                    else:
                        audio_np = native_np.copy()

                    # 放入队列
                    self.audio_queue.put(audio_np)

                    # 每 5 秒打印调试信息
                    if time.time() - last_debug_time > 5:
                        rms = np.sqrt(np.mean(audio_np ** 2))
                        print(f"[Audio] 📊 块#{read_count}: 长度={len(audio_np)}, RMS={rms:.6f}, 队列={self.audio_queue.qsize()}")
                        last_debug_time = time.time()

                except IOError as e:
                    print(f"[Audio] ⚠️ 读取异常: {e}")
                    continue

        except Exception as e:
            print(f"[Audio] ❌ 捕获异常: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()
            self.p.terminate()
            print("[Audio] 服务已停止")

    def stop(self):
        self.running = False
