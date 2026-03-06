"""Inline 查询处理器 - 修复版（按钮随机选择1个）"""

import logging
import random
import json
from typing import List

from telegram import (
    Update,
    InlineQueryResultArticle,
    InlineQueryResultCachedPhoto,
    InlineQueryResultCachedVoice,
    InputTextMessageContent,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes

import database
from utils.helpers import parse_buttons

logger = logging.getLogger(__name__)


def random_select_buttons(buttons_json: str) -> InlineKeyboardMarkup:
    """
    从按钮池中随机选择 1 个按钮
    
    Args:
        buttons_json: 按钮 JSON 字符串
        
    Returns:
        InlineKeyboardMarkup: 随机选择的 1 个按钮
    """
    if not buttons_json:
        return None
    
    try:
        # 尝试解析为按钮池格式
        buttons_data = json.loads(buttons_json)
        
        # 如果是列表（按钮池）
        if isinstance(buttons_data, list):
            # 随机选择 1 个按钮
            selected_button = random.choice(buttons_data)
            return InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    text=selected_button["text"],
                    url=selected_button["url"]
                )]
            ])
        else:
            # 兜底：使用原有的解析方式
            return parse_buttons(buttons_json)
    
    except Exception as e:
        logger.error(f"解析按钮失败: {e}")
        # 兜底：使用原有的解析方式
        return parse_buttons(buttons_json)


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
            reply_markup = random_select_buttons(msg.get("buttons"))  # ← 修改
            preview = (display_text or "（无文本）")[:100]
            
            # 优先展示语音变体
            voice_variants = database.get_message_voice_variants(msg["id"])
            image_variants = database.get_message_image_variants(msg["id"])
            
            if voice_variants:
                random_voice = random.choice(voice_variants)
                results.append(
                    InlineQueryResultCachedVoice(
                        id=f"voice_{msg['id']}",
                        voice_file_id=random_voice["file_id"],
                        title=f"🎤 {msg['key']}",
                        caption=display_text if display_text else None,
                        parse_mode="HTML" if display_text else None,
                        reply_markup=reply_markup,
                    )
                )
            elif image_variants:
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

    # 非空查询：全局按密钥查找
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

    # 未找到消息
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

    # 随机选择语音变体
    voice_variants = database.get_message_voice_variants(message["id"])
    logger.info("🎤 语音变体数量: %s", len(voice_variants))
    selected_voice = random.choice(voice_variants) if voice_variants else None
    if selected_voice:
        logger.info("🎤 随机选择语音变体 #%s", selected_voice["index"])

    # 随机选择按钮（1 个）
    reply_markup = random_select_buttons(message.get("buttons"))  # ← 修改
    if reply_markup:
        logger.info("🔘 已随机选择 1 个按钮")

    results = []

    # 优先级 1: 语音 + 图片
    if selected_voice and selected_image:
        logger.info("📤 返回：语音（后续会发图片）")
        results.append(
            InlineQueryResultCachedVoice(
                id=f"combo_voice_image_{message['id']}",
                voice_file_id=selected_voice["file_id"],
                title=f"🎤📷 {query_text}",
                caption=display_text if display_text else None,
                parse_mode="HTML" if display_text else None,
                reply_markup=reply_markup,
            )
        )
    
    # 优先级 2: 只有语音
    elif selected_voice:
        logger.info("📤 返回：纯语音")
        results.append(
            InlineQueryResultCachedVoice(
                id=f"voice_{message['id']}",
                voice_file_id=selected_voice["file_id"],
                title=f"🎤 {query_text}",
                caption=display_text if display_text else None,
                parse_mode="HTML" if display_text else None,
                reply_markup=reply_markup,
            )
        )
    
    # 优先级 3: 图片 + 文字
    elif selected_image:
        logger.info("📤 返回：图片消息")
        results.append(
            InlineQueryResultCachedPhoto(
                id=f"image_{message['id']}",
                photo_file_id=selected_image["file_id"],
                title=f"📷 {query_text}",
                description=display_text[:100] if display_text else "（纯图片）",
                caption=display_text if display_text else None,
                parse_mode="HTML" if display_text else None,
                reply_markup=reply_markup,
            )
        )
    
    # 优先级 4: 只有文字
    elif display_text:
        logger.info("📤 返回：文本消息")
        results.append(
            InlineQueryResultArticle(
                id=f"text_{message['id']}",
                title=f"📝 {query_text}",
                description=display_text[:100],
                input_message_content=InputTextMessageContent(
                    message_text=display_text,
                    parse_mode="HTML",
                ),
                reply_markup=reply_markup,
            )
        )
    
    # 优先级 5: 只有按钮
    else:
        logger.info("📤 返回：纯按钮消息")
        results.append(
            InlineQueryResultArticle(
                id=str(message["id"]),
                title=f"🔘 {query_text}",
                description="（仅按钮消息）",
                input_message_content=InputTextMessageContent(
                    message_text="👆",
                ),
                reply_markup=reply_markup,
            )
        )

    logger.info("✅ 返回 %s 条结果", len(results))
    # cache_time=0 确保每次都重新随机选择变体
    await update.inline_query.answer(results, cache_time=0, is_personal=True)
    logger.info("✅ Inline 查询处理完成\n")