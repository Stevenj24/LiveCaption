import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class Config:
    # --- OpenAI / LLM 设置 ---
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    # 获取自定义 Base URL，如果未设置则使用默认
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    # 模型选择
    # GPT_MODEL = "qwen3:4b"
    GPT_MODEL = "gpt-4o-mini"

    # 提示词
    SYSTEM_PROMPT = (
        "You are a professional simultaneous interpreter. "
        "Translate the following English text into concise, natural Chinese. "
        "Do NOT explain. Only output the translation."
    )

    # --- Whisper 语音识别设置 ---
    # 模型: tiny, small, medium, large-v3
    WHISPER_MODEL_SIZE = "small"

    # 设备: "cuda" (N卡) 或 "cpu"
    DEVICE = "cuda"
    COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"

    # --- 音频参数 ---
    SAMPLE_RATE = 16000
    CHANNELS = 1
    
    # VAD 分句参数（优化：避免过早分句）
    MIN_SILENCE_DURATION_MS = 800   # 静音阈值：800ms静音才分句（原500）
    VAD_CHUNK_SECONDS = 2.5         # 基础处理间隔：2.5秒（原1.5）
    MAX_BUFFER_SECONDS = 8.0        # 最大缓冲时间：防止无限等待
    
    # 字幕显示参数
    SUBTITLE_MAX_CHARS = 120        # 字幕最大字符数（超出则截断）

    # --- UI 样式 ---
    WINDOW_WIDTH = 1000
    WINDOW_HEIGHT = 180
    FONT_FAMILY_EN = "Segoe UI"
    FONT_SIZE_EN = 16
    COLOR_EN = "#BBBBBB"

    FONT_FAMILY_CN = "Microsoft YaHei UI"
    FONT_SIZE_CN = 24
    COLOR_CN = "#FFD700"
    FONT_WEIGHT_CN = "Bold"
    BG_COLOR = "rgba(0, 0, 0, 180)"