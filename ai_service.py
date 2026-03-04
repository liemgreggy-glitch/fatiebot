"""AI 服务模块：封装 Pollinations.AI 的文本和图片生成接口"""

import logging
import urllib.parse
from typing import List, Optional

import requests

from config import (
    POLLINATIONS_TEXT_API,
    POLLINATIONS_IMAGE_API,
    REQUEST_TIMEOUT,
    MAX_VARIANTS,
)

logger = logging.getLogger(__name__)


def rewrite_text(original_text: str) -> List[str]:
    """
    使用 Pollinations.AI 对原文进行改写，生成最多 MAX_VARIANTS 条变体。
    变体之间用 ||| 分隔。
    """
    prompt = (
        f"请改写以下文字，保持原意但使用不同的表述方式。"
        f"生成{MAX_VARIANTS}个不同版本，每个版本之间只用|||分隔，不要有其他多余内容：\n{original_text}"
    )
    encoded = urllib.parse.quote(prompt, safe="")
    url = f"{POLLINATIONS_TEXT_API}/{encoded}"
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        raw = response.text.strip()
        variants = [v.strip() for v in raw.split("|||") if v.strip()]
        return variants[:MAX_VARIANTS]
    except requests.RequestException as e:
        logger.error("AI 改写请求失败：%s", e)
        return []


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


def generate_image_url(description: str) -> str:
    """
    根据描述生成 Pollinations.AI 图片 URL（直接返回 URL，无需下载）。
    """
    encoded = urllib.parse.quote(description, safe="")
    url = f"{POLLINATIONS_IMAGE_API}/{encoded}?width=800&height=600&nologo=true"
    return url
