"""AI 创建处理器（ConversationHandler 流程）"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
from utils.keyboards import main_menu_keyboard

logger = logging.getLogger(__name__)

# 对话状态
STATE_DESCRIPTION, STATE_COUNT, STATE_PREVIEW = range(3)

KEY_DESCRIPTION = "ai_description"
KEY_VARIANTS = "ai_variants"


async def start_ai_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """进入 AI 创建流程"""
    query = update.callback_query
    await query.answer()
    _clear_ai_data(context)
    await query.edit_message_text(
        "🎨 <b>AI 创建</b>\n\n请描述你的产品或服务，AI 将自动生成多条宣传文案变体。\n\n"
        "示例：<i>高端护肤品，主打保湿补水，适合干性肌肤</i>",
        parse_mode="HTML",
    )
    return STATE_DESCRIPTION


async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """接收描述，询问生成数量"""
    description = update.message.text.strip()
    if not description:
        await update.message.reply_text("❌ 描述不能为空，请重新输入：")
        return STATE_DESCRIPTION

    context.user_data[KEY_DESCRIPTION] = description

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("10 条", callback_data="ai_count_10"),
            InlineKeyboardButton("20 条", callback_data="ai_count_20"),
        ],
        [InlineKeyboardButton("❌ 取消", callback_data="cancel")],
    ])
    await update.message.reply_text(
        "📊 选择生成数量：",
        reply_markup=keyboard,
    )
    return STATE_COUNT


async def generate_variants_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """生成文案变体"""
    query = update.callback_query
    await query.answer()

    count = int(query.data.split("_")[-1])
    description = context.user_data.get(KEY_DESCRIPTION, "")

    await query.edit_message_text(f"⏳ AI 正在生成 {count} 条文案，请稍候...")

    variants = ai_service.generate_text_variants(description, count=count)

    if not variants or len(variants) < 3:  # minimum viable variant count for preview
        await query.edit_message_text(
            "❌ 生成失败，请重试。",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    context.user_data[KEY_VARIANTS] = variants

    preview = f"✅ <b>已生成 {len(variants)} 条文案！</b>\n\n预览：\n\n"
    for i, v in enumerate(variants[:3], 1):
        preview += f"<b>{i}.</b> {v[:100]}{'...' if len(v) > 100 else ''}\n\n"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💾 保存", callback_data="ai_save"),
            InlineKeyboardButton("🔄 重新生成", callback_data=f"ai_count_{count}"),
        ],
        [InlineKeyboardButton("❌ 取消", callback_data="cancel")],
    ])

    await query.edit_message_text(preview, parse_mode="HTML", reply_markup=keyboard)
    return STATE_PREVIEW


async def save_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """保存 AI 生成的消息"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    variants = context.user_data.get(KEY_VARIANTS, [])

    if not variants:
        await query.edit_message_text(
            "❌ 没有可保存的内容",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    key = generate_key()
    text = variants[0]
    msg_id = database.create_message(user_id, key, text, None, None)

    if not msg_id:
        await query.edit_message_text(
            "❌ 保存失败，请稍后重试。",
            reply_markup=main_menu_keyboard(),
        )
        _clear_ai_data(context)
        return ConversationHandler.END

    for variant in variants:
        database.add_message_variant(msg_id, variant)

    try:
        await query.message.delete()
    except Exception:
        pass

    await context.bot.send_message(
        chat_id=user_id,
        text=(
            f"✅ <b>消息已保存！</b>\n\n"
            f"🔑 密钥：<code>{key}</code>\n"
            f"📝 文案变体：{len(variants)} 条\n\n"
            f"💡 在任意聊天中输入 @机器人用户名 {key} 即可发送此消息。"
        ),
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )

    _clear_ai_data(context)
    return ConversationHandler.END


def _clear_ai_data(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(KEY_DESCRIPTION, None)
    context.user_data.pop(KEY_VARIANTS, None)


async def cancel_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """取消 AI 创建"""
    _clear_ai_data(context)
    if update.callback_query:
        await update.callback_query.answer()
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
            STATE_COUNT: [
                CallbackQueryHandler(generate_variants_callback, pattern="^ai_count_"),
            ],
            STATE_PREVIEW: [
                CallbackQueryHandler(save_ai_message, pattern="^ai_save$"),
                CallbackQueryHandler(generate_variants_callback, pattern="^ai_count_"),
                CallbackQueryHandler(cancel_ai, pattern="^(cancel|main_menu)$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_ai),
            CallbackQueryHandler(cancel_ai, pattern="^cancel$"),
        ],
        allow_reentry=True,
    )
