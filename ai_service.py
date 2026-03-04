"""AI 服务模块：封装 Pollinations.AI 的文本生成接口"""

import logging
import urllib.parse
from typing import List, Optional

import requests

from config import (
    POLLINATIONS_TEXT_API,
    REQUEST_TIMEOUT,
    MAX_VARIANTS,
)

logger = logging.getLogger(__name__)


def rewrite_text(original_text: str) -> List[str]:
    """
    使用 Pollinations.AI 对原文进行改写，生成最多 MAX_VARIANTS 条变体。
    变体之间用 ||| 分隔。
    """
    return generate_text_variants(original_text, count=MAX_VARIANTS)


def generate_ad_text(description: str) -> Optional[str]:
    """
    根据产品/服务描述，使用 Pollinations.AI 生成吸引人的宣传文案。
    """
    prompt = (
        f"请根据以下产品/服务描述，生成一段简洁、吸引人的中文宣传文案（100字以内）：\n{description}"
    )
    encoded = urllib.parse.quote(prompt, safe="")
    url = f"{POLLINATIONS_TEXT_API}/{encoded}"
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.text.strip()
    except requests.RequestException as e:
        logger.error("AI 文案生成失败：%s", e)
        return None


def generate_text_variants(original_text: str, count: int = 10) -> List[str]:
    """
    生成文本变体。

    Args:
        original_text: 原始文本
        count: 生成数量

    Returns:
        list: 变体列表
    """
    prompt = (
        f"请将以下文字改写成{count}个不同版本，保持核心意思不变。\n"
        f"要求：\n"
        f"1. 每个版本用|||分隔\n"
        f"2. 不要添加编号\n"
        f"3. 每个版本都要完整且流畅\n"
        f"4. 使用不同的词汇和句式\n\n"
        f"原文：{original_text}\n\n"
        f"请输出{count}个版本："
    )
    encoded = urllib.parse.quote(prompt, safe="")
    url = f"{POLLINATIONS_TEXT_API}/{encoded}"
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT * 2)  # variant generation needs more time
        response.raise_for_status()
        raw = response.text.strip()
        logger.info("AI 返回: %s", raw[:200])
        variants = [v.strip() for v in raw.split("|||") if v.strip()]
        if len(variants) < 3:
            variants = [v.strip() for v in raw.split("\n") if v.strip() and len(v) > 10]
        logger.info("成功生成 %d 条变体", len(variants))
        return variants[:count]
    except requests.RequestException as e:
        logger.error("生成文案变体失败：%s", e)
        return []
