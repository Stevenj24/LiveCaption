import os
# 关键修复：允许 OpenMP 库重复加载，解决 Error #15
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import sys
import signal
# ... 后面的代码保持不变 ...
from queue import Queue
from PyQt6.QtWidgets import QApplication

# 导入模块
from modules.ui import OverlayWindow
from modules.audio import AudioCapture
from modules.asr import ASRWorker
from modules.llm import LLMWorker

# 处理 Ctrl+C
signal.signal(signal.SIGINT, signal.SIG_DFL)


def main():
    print("=== 启动实时双语字幕系统 ===")

    app = QApplication(sys.argv)

    # 1. 初始化 UI
    window = OverlayWindow()
    window.show()

    # 2. 队列初始化
    audio_queue = Queue()

    # 3. 初始化线程
    thread_audio = AudioCapture(audio_queue)
    thread_asr = ASRWorker(audio_queue)
    thread_llm = LLMWorker()

    # 4. 连接信号 (流水线)
    # ASR -> UI (显示英文)
    thread_asr.text_recognized.connect(window.update_en)
    # ASR -> LLM (发送去翻译)
    thread_asr.text_recognized.connect(thread_llm.add_text)
    # LLM -> UI (显示中文)
    thread_llm.translation_updated.connect(window.update_cn)

    # 5. 启动线程
    thread_llm.start()
    thread_asr.start()
    thread_audio.start()

    print(">>> 系统运行中。双击窗口退出。")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()