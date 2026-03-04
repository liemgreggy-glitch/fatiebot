"""AI 创建处理器（ConversationHandler 流程）"""

import logging

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

import database
import ai_service
from utils.helpers import generate_key
from utils.keyboards import ai_create_confirm_keyboard, main_menu_keyboard

logger = logging.getLogger(__name__)

# 对话状态
STATE_DESCRIPTION, STATE_PREVIEW = range(2)

KEY_DESCRIPTION = "ai_description"
KEY_AD_TEXT = "ai_ad_text"
KEY_IMAGE_URL = "ai_image_url"


async def start_ai_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """进入 AI 创建流程"""
    query = update.callback_query
    await query.answer()
    context.user_data.pop(KEY_DESCRIPTION, None)
    context.user_data.pop(KEY_AD_TEXT, None)
    context.user_data.pop(KEY_IMAGE_URL, None)
    await query.edit_message_text(
        "🎨 <b>AI 创建</b>\n\n请描述你的产品或服务，AI 将自动生成宣传文案和配图。\n\n"
        "示例：<i>高端护肤品，主打保湿补水，适合干性肌肤</i>",
        parse_mode="HTML",
    )
    return STATE_DESCRIPTION


async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """接收产品描述，调用 AI 生成"""
    description = update.message.text.strip()
    if not description:
        await update.message.reply_text("❌ 描述不能为空，请重新输入：")
        return STATE_DESCRIPTION

    context.user_data[KEY_DESCRIPTION] = description
    await update.message.reply_text("⏳ AI 正在创作中，请稍候...")

    # 生成文案
    ad_text = ai_service.generate_ad_text(description)
    if not ad_text:
        await update.message.reply_text(
            "❌ AI 文案生成失败，请稍后重试。",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    # 生成图片 URL
    image_url = ai_service.generate_image_url(description)

    context.user_data[KEY_AD_TEXT] = ad_text
    context.user_data[KEY_IMAGE_URL] = image_url

    await _show_ai_preview(update.message, ad_text, image_url)
    return STATE_PREVIEW


async def _show_ai_preview(msg, ad_text: str, image_url: str) -> None:
    """展示 AI 生成结果预览"""
    caption = (
        f"🤖 <b>AI 生成结果</b>\n\n"
        f"📝 宣传文案：\n{ad_text}\n\n"
        f"请选择操作："
    )
    try:
        await msg.reply_photo(
            photo=image_url,
            caption=caption,
            parse_mode="HTML",
            reply_markup=ai_create_confirm_keyboard(),
        )
    except Exception:
        # 图片加载失败时降级为纯文本
        await msg.reply_text(
            caption + f"\n\n🖼 图片：{image_url}",
            parse_mode="HTML",
            reply_markup=ai_create_confirm_keyboard(),
        )


async def save_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """保存 AI 生成的消息"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    text = context.user_data.get(KEY_AD_TEXT)
    image_url = context.user_data.get(KEY_IMAGE_URL)
    key = generate_key()
    msg_id = database.create_message(user_id, key, text, image_url)
    if msg_id:
        await query.edit_message_caption(
            f"✅ <b>AI 消息已保存！</b>\n\n"
            f"🔑 密钥：<code>{key}</code>\n\n"
            f"💡 在任意聊天中输入 @机器人用户名 {key} 即可发送此消息。",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
    else:
        try:
            await query.edit_message_caption(
                "❌ 保存失败，请稍后重试。",
                reply_markup=main_menu_keyboard(),
            )
        except Exception:
            await query.edit_message_text(
                "❌ 保存失败，请稍后重试。",
                reply_markup=main_menu_keyboard(),
            )
    _clear_ai_data(context)
    return ConversationHandler.END


async def regenerate_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """重新生成 AI 内容"""
    query = update.callback_query
    await query.answer("⏳ 重新生成中...")
    description = context.user_data.get(KEY_DESCRIPTION, "")
    if not description:
        await query.edit_message_text("❌ 描述丢失，请重新开始。", reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    try:
        await query.edit_message_caption("⏳ AI 正在重新创作中，请稍候...")
    except Exception:
        await query.edit_message_text("⏳ AI 正在重新创作中，请稍候...")

    ad_text = ai_service.generate_ad_text(description)
    if not ad_text:
        try:
            await query.edit_message_caption("❌ AI 文案生成失败，请稍后重试。", reply_markup=main_menu_keyboard())
        except Exception:
            await query.edit_message_text("❌ AI 文案生成失败，请稍后重试。", reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    image_url = ai_service.generate_image_url(description)
    context.user_data[KEY_AD_TEXT] = ad_text
    context.user_data[KEY_IMAGE_URL] = image_url

    caption = (
        f"🤖 <b>AI 生成结果</b>\n\n"
        f"📝 宣传文案：\n{ad_text}\n\n"
        f"请选择操作："
    )
    try:
        await query.edit_message_media_and_caption(caption)
    except Exception:
        pass
    try:
        await query.edit_message_caption(
            caption,
            parse_mode="HTML",
            reply_markup=ai_create_confirm_keyboard(),
        )
    except Exception:
        await query.edit_message_text(
            caption + f"\n\n🖼 图片：{image_url}",
            parse_mode="HTML",
            reply_markup=ai_create_confirm_keyboard(),
        )
    return STATE_PREVIEW


def _clear_ai_data(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(KEY_DESCRIPTION, None)
    context.user_data.pop(KEY_AD_TEXT, None)
    context.user_data.pop(KEY_IMAGE_URL, None)


async def cancel_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """取消 AI 创建"""
    _clear_ai_data(context)
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_caption(
                "已取消。", reply_markup=main_menu_keyboard()
            )
        except Exception:
            await update.callback_query.edit_message_text(
                "已取消。", reply_markup=main_menu_keyboard()
            )
    elif update.message:
        await update.message.reply_text("已取消。", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


def ai_create_conversation_handler() -> ConversationHandler:
    """构建 AI 创建的 ConversationHandler"""
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_ai_create, pattern="^ai_create$")],
        states={
            STATE_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description)
            ],
            STATE_PREVIEW: [
                CallbackQueryHandler(save_ai_message, pattern="^ai_save$"),
                CallbackQueryHandler(regenerate_ai, pattern="^ai_regenerate$"),
                CallbackQueryHandler(cancel_ai, pattern="^main_menu$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_ai),
            CallbackQueryHandler(cancel_ai, pattern="^cancel$"),
        ],
        allow_reentry=True,
    )
