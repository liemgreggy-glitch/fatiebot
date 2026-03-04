"""数据验证模块"""

import json
import re
from typing import Optional, Tuple


def validate_button_input(raw: str) -> Tuple[bool, str]:
    """
    验证按钮输入格式（文字|链接，每行一个）。
    返回 (是否合法, 错误信息)。
    """
    if not raw.strip():
        return False, "按钮内容不能为空"

    for i, line in enumerate(raw.strip().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if "|" not in line:
            return False, f"第 {i} 行格式错误，请使用「文字|链接」格式"
        parts = line.split("|", 1)
        if not parts[0].strip():
            return False, f"第 {i} 行按钮文字不能为空"
        url = parts[1].strip()
        if not url.startswith(("http://", "https://")):
            return False, f"第 {i} 行链接必须以 http:// 或 https:// 开头"
    return True, ""


def validate_message_text(text: str) -> Tuple[bool, str]:
    """验证消息文本是否合法"""
    if not text.strip():
        return False, "消息文本不能为空"
    if len(text) > 4096:
        return False, "消息文本不能超过 4096 个字符"
    return True, ""


def validate_key(key: str) -> Tuple[bool, str]:
    """验证密钥格式"""
    if not re.match(r"^[a-z0-9]{4,16}$", key):
        return False, "密钥只能包含小写字母和数字，长度 4-16 位"
    return True, ""
