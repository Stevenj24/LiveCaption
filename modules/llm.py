from queue import Queue, Empty
from PyQt6.QtCore import QThread, pyqtSignal
from openai import OpenAI
from config import Config


class LLMWorker(QThread):
    translation_updated = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.input_queue = Queue()
        self.running = True
        self.client = None

    def add_text(self, text):
        self.input_queue.put(text)

    def run(self):
        if not Config.OPENAI_API_KEY:
            print("[LLM] ⚠️ 未配置 API Key")
            return

        print(f"[LLM] 初始化 Base URL: {Config.OPENAI_BASE_URL}")

        try:
            self.client = OpenAI(
                api_key=Config.OPENAI_API_KEY,
                base_url=Config.OPENAI_BASE_URL
            )
        except Exception as e:
            print(f"[LLM] 初始化失败: {e}")
            return

        while self.running:
            try:
                text = self.input_queue.get(timeout=1)
                self._translate(text)
            except Empty:
                continue
            except Exception as e:
                print(f"[LLM] 错误: {e}")

    def _translate(self, text):
        try:
            stream = self.client.chat.completions.create(
                model=Config.GPT_MODEL,
                messages=[
                    {"role": "system", "content": Config.SYSTEM_PROMPT},
                    {"role": "user", "content": text}
                ],
                stream=True
            )

            full_result = ""
            for chunk in stream:
                if not self.running: break
                # 防御性检查：某些 chunk 可能没有 choices 或 delta
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        full_result += delta.content

            print(f"[LLM] 🇨🇳: {full_result}")
            self.translation_updated.emit(full_result)

        except Exception as e:
            print(f"[LLM] 请求失败: {e}")

    def stop(self):
        self.running = False