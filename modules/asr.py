import time
import numpy as np
from queue import Queue, Empty
from PyQt6.QtCore import QThread, pyqtSignal
from faster_whisper import WhisperModel
from config import Config


class ASRWorker(QThread):
    text_recognized = pyqtSignal(str)

    def __init__(self, audio_queue: Queue):
        super().__init__()
        self.audio_queue = audio_queue
        self.running = True
        self.model = None
        
        # 文本缓冲（用于合并片段）
        self.text_buffer = ""
        self.last_emit_time = 0

    def run(self):
        print(f"[Whisper] 加载模型: {Config.WHISPER_MODEL_SIZE}...")
        try:
            self.model = WhisperModel(
                Config.WHISPER_MODEL_SIZE,
                device=Config.DEVICE,
                compute_type=Config.COMPUTE_TYPE
            )
            print("[Whisper] ✅ 模型就绪")
        except Exception as e:
            print(f"[Whisper] ❌ 加载失败: {e}")
            return

        audio_buffer = np.array([], dtype=np.float32)
        
        # 阈值计算
        min_chunk_samples = int(Config.SAMPLE_RATE * Config.VAD_CHUNK_SECONDS)
        max_chunk_samples = int(Config.SAMPLE_RATE * Config.MAX_BUFFER_SECONDS)
        
        buffer_start_time = time.time()
        silence_start_time = None
        
        # 静音检测阈值（RMS 能量）
        SILENCE_THRESHOLD = 0.01
        SILENCE_DURATION_FOR_SPLIT = Config.MIN_SILENCE_DURATION_MS / 1000.0

        debug_counter = 0
        
        while self.running:
            try:
                chunk = self.audio_queue.get(timeout=0.5)
                audio_buffer = np.concatenate((audio_buffer, chunk))
                
                # 检测当前 chunk 是否为静音
                chunk_rms = np.sqrt(np.mean(chunk ** 2))
                is_silence = chunk_rms < SILENCE_THRESHOLD
                
                # 调试日志：每10次处理打印一次状态
                debug_counter += 1
                if debug_counter % 10 == 0:
                    buffer_sec = len(audio_buffer) / Config.SAMPLE_RATE
                    print(f"[ASR] 📊 DEBUG: chunk_rms={chunk_rms:.6f}, 静音={is_silence}, 缓冲={buffer_sec:.1f}s, 阈值={SILENCE_THRESHOLD}")
                
                current_time = time.time()
                buffer_duration = len(audio_buffer) / Config.SAMPLE_RATE
                
                # 静音计时
                if is_silence:
                    if silence_start_time is None:
                        silence_start_time = current_time
                    silence_duration = current_time - silence_start_time
                else:
                    silence_start_time = None
                    silence_duration = 0
                
                # 决定是否触发识别的条件
                should_transcribe = False
                reason = ""
                
                # 条件1: 检测到足够长的静音 且 缓冲区有足够内容
                if silence_duration >= SILENCE_DURATION_FOR_SPLIT and len(audio_buffer) >= min_chunk_samples:
                    should_transcribe = True
                    reason = f"静音 {silence_duration:.1f}s"
                
                # 条件2: 缓冲区超过最大长度（兜底）
                elif len(audio_buffer) >= max_chunk_samples:
                    should_transcribe = True
                    reason = f"缓冲区满 {buffer_duration:.1f}s"
                
                if should_transcribe:
                    print(f"[ASR] 触发识别 ({reason})")
                    self._transcribe(audio_buffer)
                    audio_buffer = np.array([], dtype=np.float32)
                    buffer_start_time = time.time()
                    silence_start_time = None
                    
            except Empty:
                # 超时但缓冲区有内容，检查是否应该处理
                if len(audio_buffer) > 0:
                    elapsed = time.time() - buffer_start_time
                    # 如果超过最大等待时间的一半，且有内容，处理它
                    if elapsed > Config.MAX_BUFFER_SECONDS / 2 and len(audio_buffer) >= min_chunk_samples // 2:
                        print(f"[ASR] 超时处理 ({elapsed:.1f}s)")
                        self._transcribe(audio_buffer)
                        audio_buffer = np.array([], dtype=np.float32)
                        buffer_start_time = time.time()
                continue
            except Exception as e:
                print(f"[ASR] 错误: {e}")

    def _transcribe(self, audio_data):
        if not self.model:
            return

        try:
            # 使用内置 VAD 过滤
            segments, info = self.model.transcribe(
                audio_data,
                beam_size=1,
                language="en",
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=Config.MIN_SILENCE_DURATION_MS)
            )

            text = " ".join([s.text for s in segments]).strip()
            
            if text:
                # 智能合并：如果上次发送不久且文本较短，尝试合并
                current_time = time.time()
                time_since_last = current_time - self.last_emit_time
                
                # 如果距离上次发送不到2秒，且文本看起来不完整，累积
                if time_since_last < 2.0 and not self._looks_complete(self.text_buffer) and len(self.text_buffer) < 80:
                    self.text_buffer = (self.text_buffer + " " + text).strip()
                    print(f"[ASR] 📝 累积: {self.text_buffer}")
                else:
                    # 发送之前累积的内容
                    if self.text_buffer:
                        combined = (self.text_buffer + " " + text).strip()
                        print(f"[ASR] 👂: {combined}")
                        self.text_recognized.emit(combined)
                        self.text_buffer = ""
                    else:
                        print(f"[ASR] 👂: {text}")
                        self.text_recognized.emit(text)
                    
                    self.last_emit_time = current_time
                    
        except Exception as e:
            print(f"[ASR] 识别错误: {e}")
    
    def _looks_complete(self, text: str) -> bool:
        """判断文本是否看起来完整（以句子结束符结尾）"""
        if not text:
            return True
        text = text.rstrip()
        return text.endswith(('.', '!', '?', '。', '！', '？', '"', "'"))

    def stop(self):
        self.running = False
        # 清空残余缓冲
        if self.text_buffer:
            print(f"[ASR] 👂 (结束): {self.text_buffer}")
            self.text_recognized.emit(self.text_buffer)
            self.text_buffer = ""
