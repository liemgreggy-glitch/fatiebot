"""辅助函数模块"""

import json
import random
import string
import logging
from typing import Optional, List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import database

logger = logging.getLogger(__name__)


def generate_key(length: int = 6) -> str:
    """生成随机唯一密钥（保证数据库内唯一）"""
    chars = string.ascii_lowercase + string.digits
    for _ in range(10):  # 最多重试 10 次
        key = "".join(random.choices(chars, k=length))
        if not database.key_exists(key):
            return key
    # 极小概率退路：增加长度
    return "".join(random.choices(chars, k=length + 2))


def parse_buttons(buttons_json: Optional[str]) -> Optional[InlineKeyboardMarkup]:
    """
    将 JSON 字符串解析为 InlineKeyboardMarkup。
    格式：[{"text": "按钮文字", "url": "https://..."}]
    或每行一个按钮：[{"text": "...", "url": "..."}, ...]
    """
    if not buttons_json:
        return None
    try:
        data = json.loads(buttons_json)
        keyboard: List[List[InlineKeyboardButton]] = []
        for item in data:
            if isinstance(item, dict):
                btn = InlineKeyboardButton(
                    text=item.get("text", "按钮"),
                    url=item.get("url"),
                    callback_data=item.get("callback_data"),
                )
                keyboard.append([btn])
        return InlineKeyboardMarkup(keyboard) if keyboard else None
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("按钮解析失败：%s", e)
        return None


def format_buttons_input(raw: str) -> Optional[str]:
    """
    将用户输入的按钮文本（格式：文字|链接，每行一个）转换为 JSON 字符串。
    """
    buttons = []
    for line in raw.strip().splitlines():
        line = line.strip()
        if "|" in line:
            parts = line.split("|", 1)
            text = parts[0].strip()
            url = parts[1].strip()
            if text and url:
                buttons.append({"text": text, "url": url})
    if not buttons:
        return None
    return json.dumps(buttons, ensure_ascii=False)


def random_variant(variants: List[str]) -> Optional[str]:
    """从变体列表中随机返回一条"""
    if not variants:
        return None
    return random.choice(variants)
