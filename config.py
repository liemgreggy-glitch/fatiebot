"""配置文件：从环境变量读取机器人配置"""

import os
import logging
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# Telegram Bot Token
BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

# 数据库路径
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./data/bot.db")

# 日志级别
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# 每页消息条数
PAGE_SIZE: int = 5

# 密钥长度
KEY_LENGTH: int = 6

# AI 变体最大数量
MAX_VARIANTS: int = 10

# Pollinations.AI API 端点
POLLINATIONS_TEXT_API: str = "https://text.pollinations.ai"
POLLINATIONS_IMAGE_API: str = "https://image.pollinations.ai/prompt"

# 请求超时（秒）
REQUEST_TIMEOUT: int = 30


def setup_logging() -> None:
    """配置日志系统"""
    numeric_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=numeric_level,
    )
