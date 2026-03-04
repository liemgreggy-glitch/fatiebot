"""Inline 查询处理器"""

import logging
import random
from typing import List

from telegram import (
    Update,
    InlineQueryResultArticle,
    InlineQueryResultPhoto,
    InputTextMessageContent,
)
from telegram.ext import ContextTypes

import database
from utils.helpers import parse_buttons

logger = logging.getLogger(__name__)


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 inline 查询。
    用户在聊天中输入 @机器人用户名 密钥，机器人返回匹配的消息模板。
    """
    query_text = update.inline_query.query.strip()
    user_id = update.inline_query.from_user.id

    if not query_text:
        # 空查询：展示最近的几条消息
        messages = database.get_user_messages(user_id, page=1, page_size=5)
    else:
        # 按密钥或文本内容搜索
        messages = database.search_user_messages(user_id, query_text)

    results: List = []
    for msg in messages:
        # 优先使用变体，否则使用原文
        variants = database.get_variants(msg["id"])
        if variants:
            display_text = random.choice(variants)
        else:
            display_text = msg.get("text") or ""

        reply_markup = parse_buttons(msg.get("buttons"))
        preview = (display_text or "（无文本）")[:100]
        description = f"🔑 {msg['key']} | {preview}"

        image_url = msg.get("image_url")
        # 过滤掉 tg:// 协议的 file_id（inline 模式不支持）
        if image_url and image_url.startswith("tg://"):
            image_url = None

        if image_url:
            results.append(
                InlineQueryResultPhoto(
                    id=str(msg["id"]),
                    photo_url=image_url,
                    thumbnail_url=image_url,
                    title=f"📨 {msg['key']}",
                    description=preview,
                    caption=display_text,
                    reply_markup=reply_markup,
                )
            )
        else:
            results.append(
                InlineQueryResultArticle(
                    id=str(msg["id"]),
                    title=f"📨 {msg['key']}",
                    description=description,
                    input_message_content=InputTextMessageContent(
                        message_text=display_text or "（无内容）",
                    ),
                    reply_markup=reply_markup,
                )
            )

    await update.inline_query.answer(results, cache_time=0)
