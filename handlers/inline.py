"""Inline 查询处理器"""

import logging
import random
from typing import List

from telegram import (
    Update,
    InlineQueryResultArticle,
    InlineQueryResultCachedPhoto,
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
    支持所有用户（包括新账号）通过密钥查询任意消息。
    """
    user = update.inline_query.from_user
    query_text = update.inline_query.query.strip()

    logger.info("=" * 60)
    logger.info("🔍 收到 Inline 查询")
    logger.info("   用户 ID: %s", user.id)
    logger.info("   用户名: @%s", user.username or "(无)")
    logger.info("   姓名: %s %s", user.first_name, user.last_name or "")
    logger.info("   查询内容: '%s'", query_text)
    logger.info("=" * 60)

    # 处理空查询：展示当前用户最近的消息
    if not query_text:
        logger.info("查询为空，返回用户最近消息")
        messages = database.get_user_messages(user.id, page=1, page_size=5)
        results: List = []
        for msg in messages:
            variants = database.get_variants(msg["id"])
            display_text = random.choice(variants) if variants else (msg.get("text") or "")
            reply_markup = parse_buttons(msg.get("buttons"))
            preview = (display_text or "（无文本）")[:100]
            image_variants = database.get_message_image_variants(msg["id"])
            if image_variants:
                random_image = random.choice(image_variants)
                results.append(
                    InlineQueryResultCachedPhoto(
                        id=str(msg["id"]),
                        photo_file_id=random_image["file_id"],
                        caption=display_text if display_text else None,
                        parse_mode="HTML" if display_text else None,
                        reply_markup=reply_markup,
                    )
                )
            else:
                results.append(
                    InlineQueryResultArticle(
                        id=str(msg["id"]),
                        title=f"📨 {msg['key']}",
                        description=f"🔑 {msg['key']} | {preview}",
                        input_message_content=InputTextMessageContent(
                            message_text=display_text or "（无内容）",
                        ),
                        reply_markup=reply_markup,
                    )
                )
        await update.inline_query.answer(results, cache_time=0, is_personal=True)
        return

    # 非空查询：全局按密钥查找（任何用户创建的消息都可以查到）
    logger.info("📊 全局查询密钥: '%s'", query_text)

    try:
        message = database.get_message_by_key_global(query_text)
        logger.info("📦 数据库结果: %s", message)
    except Exception as e:
        logger.error("❌ 数据库查询失败: %s", e)
        results = [
            InlineQueryResultArticle(
                id="error",
                title="❌ 查询失败",
                description="数据库错误，请稍后重试",
                input_message_content=InputTextMessageContent(
                    message_text="❌ 系统错误，请稍后重试"
                ),
            )
        ]
        await update.inline_query.answer(results, cache_time=0)
        return

    # 未找到消息：显示友好提示
    if not message:
        logger.warning("⚠️ 未找到密钥: '%s'", query_text)
        results = [
            InlineQueryResultArticle(
                id="not_found",
                title=f"❌ 未找到密钥: {query_text}",
                description="请检查密钥是否正确",
                input_message_content=InputTextMessageContent(
                    message_text=(
                        f"❌ <b>未找到密钥</b>\n\n"
                        f"密钥: <code>{query_text}</code>\n\n"
                        "💡 请检查：\n"
                        "• 密钥拼写是否正确\n"
                        "• 消息是否已被删除\n"
                        "• 是否输入了多余的空格"
                    ),
                    parse_mode="HTML",
                ),
            )
        ]
        await update.inline_query.answer(
            results,
            cache_time=5,
            is_personal=True,
            switch_pm_text="📋 创建新消息",
            switch_pm_parameter="create",
        )
        return

    # 找到消息：构建发送内容
    logger.info("✅ 找到消息 ID: %s", message["id"])

    # 随机选择文案变体
    variants = database.get_variants(message["id"])
    logger.info("📝 文案变体数量: %s", len(variants))
    if variants:
        display_text = random.choice(variants)
        logger.info("📝 随机选择文案变体: %s...", display_text[:50])
    else:
        display_text = message.get("text") or ""
        logger.info("📝 使用原始文案: %s...", display_text[:50] if display_text else "(无)")

    # 随机选择图片变体
    image_variants = database.get_message_image_variants(message["id"])
    logger.info("🖼 图片变体数量: %s", len(image_variants))
    selected_image = random.choice(image_variants) if image_variants else None
    if selected_image:
        logger.info("🖼 随机选择图片变体 #%s", selected_image["index"])

    # 解析按钮
    reply_markup = parse_buttons(message.get("buttons"))

    results = []

    if selected_image:
        logger.info("📤 构建图片消息")
        results.append(
            InlineQueryResultCachedPhoto(
                id=str(message["id"]),
                photo_file_id=selected_image["file_id"],
                caption=display_text if display_text else None,
                parse_mode="HTML" if display_text else None,
                reply_markup=reply_markup,
            )
        )
    elif display_text:
        logger.info("📤 构建文本消息")
        results.append(
            InlineQueryResultArticle(
                id=str(message["id"]),
                title=f"📤 发送: {query_text}",
                description=display_text[:100],
                input_message_content=InputTextMessageContent(
                    message_text=display_text,
                    parse_mode="HTML",
                ),
                reply_markup=reply_markup,
            )
        )
    else:
        logger.warning("⚠️ 消息无内容（无文案、无图片）")
        results.append(
            InlineQueryResultArticle(
                id=str(message["id"]),
                title=f"📤 发送: {query_text}",
                description="（仅按钮消息）",
                input_message_content=InputTextMessageContent(
                    message_text="（仅按钮）",
                ),
                reply_markup=reply_markup,
            )
        )

    logger.info("✅ 返回 %s 条结果", len(results))
    # cache_time=0 确保每次都重新随机选择变体
    await update.inline_query.answer(results, cache_time=0, is_personal=True)
    logger.info("✅ Inline 查询处理完成\n")
