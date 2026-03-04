"""创建消息处理器（ConversationHandler 流程）"""

import logging
from typing import Optional

from telegram import Update, Message
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

import database
from utils.helpers import generate_key, parse_buttons, format_buttons_input
from utils.keyboards import (
    yes_no_keyboard,
    create_confirm_keyboard,
    main_menu_keyboard,
)
from utils.validators import validate_message_text, validate_button_input

logger = logging.getLogger(__name__)

# 对话状态
(
    STATE_TEXT,
    STATE_IMAGE,
    STATE_BUTTONS,
    STATE_CONFIRM,
) = range(4)

# context.user_data 键名
KEY_TEXT = "draft_text"
KEY_IMAGE = "draft_image"
KEY_BUTTONS = "draft_buttons"


async def start_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """进入创建消息流程"""
    query = update.callback_query
    await query.answer()
    # 清空草稿
    context.user_data.pop(KEY_TEXT, None)
    context.user_data.pop(KEY_IMAGE, None)
    context.user_data.pop(KEY_BUTTONS, None)
    await query.edit_message_text("✍️ 请发送消息文本内容：")
    return STATE_TEXT


async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """接收消息文本"""
    text = update.message.text
    valid, err = validate_message_text(text)
    if not valid:
        await update.message.reply_text(f"❌ {err}\n请重新发送消息文本：")
        return STATE_TEXT
    context.user_data[KEY_TEXT] = text
    await update.message.reply_text(
        "🖼 是否添加图片？",
        reply_markup=yes_no_keyboard("add_image_yes", "add_image_no"),
    )
    return STATE_IMAGE


async def ask_image_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """用户选择添加图片"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🖼 请发送图片：")
    return STATE_IMAGE


async def ask_image_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """用户选择不添加图片"""
    query = update.callback_query
    await query.answer()
    context.user_data.pop(KEY_IMAGE, None)
    await query.edit_message_text(
        "🔘 是否添加按钮？",
        reply_markup=yes_no_keyboard("add_buttons_yes", "add_buttons_no"),
    )
    return STATE_BUTTONS


async def receive_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """接收图片"""
    if update.message.photo:
        # 取最大尺寸的图片
        file = update.message.photo[-1]
        file_id = file.file_id
        context.user_data[KEY_IMAGE] = f"tg://file_id/{file_id}"
    elif update.message.document and update.message.document.mime_type.startswith("image/"):
        file_id = update.message.document.file_id
        context.user_data[KEY_IMAGE] = f"tg://file_id/{file_id}"
    else:
        await update.message.reply_text("❌ 请发送图片文件")
        return STATE_IMAGE
    await update.message.reply_text(
        "🔘 是否添加按钮？",
        reply_markup=yes_no_keyboard("add_buttons_yes", "add_buttons_no"),
    )
    return STATE_BUTTONS


async def ask_buttons_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """用户选择添加按钮"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔘 请按以下格式输入按钮（每行一个）：\n"
        "<code>按钮文字|https://链接</code>\n\n"
        "示例：\n"
        "<code>点击了解|https://example.com\n立即购买|https://shop.com</code>",
        parse_mode="HTML",
    )
    return STATE_BUTTONS


async def ask_buttons_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """用户选择不添加按钮"""
    query = update.callback_query
    await query.answer()
    context.user_data.pop(KEY_BUTTONS, None)
    return await _show_preview(query, context)


async def receive_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """接收按钮内容"""
    raw = update.message.text
    valid, err = validate_button_input(raw)
    if not valid:
        await update.message.reply_text(
            f"❌ {err}\n请重新输入按钮（每行一个，格式：文字|链接）："
        )
        return STATE_BUTTONS
    context.user_data[KEY_BUTTONS] = format_buttons_input(raw)
    return await _show_preview(update.message, context)


async def _show_preview(msg_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """显示消息预览"""
    text = context.user_data.get(KEY_TEXT, "（无文本）")
    image = context.user_data.get(KEY_IMAGE)
    buttons_json = context.user_data.get(KEY_BUTTONS)
    buttons = parse_buttons(buttons_json)

    preview_lines = ["📋 <b>消息预览</b>\n"]
    preview_lines.append(f"📝 文字：{text[:100]}{'...' if len(text) > 100 else ''}")
    preview_lines.append(f"🖼 图片：{'✅ 已添加' if image else '❌ 未添加'}")
    preview_lines.append(f"🔘 按钮：{'✅ 已添加' if buttons_json else '❌ 未添加'}")

    preview_text = "\n".join(preview_lines)
    keyboard = create_confirm_keyboard()

    if hasattr(msg_or_query, "edit_message_text"):
        await msg_or_query.edit_message_text(
            preview_text, parse_mode="HTML", reply_markup=keyboard
        )
    else:
        await msg_or_query.reply_text(
            preview_text, parse_mode="HTML", reply_markup=keyboard
        )
    return STATE_CONFIRM


async def save_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """保存消息到数据库"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    text = context.user_data.get(KEY_TEXT)
    image = context.user_data.get(KEY_IMAGE)
    buttons = context.user_data.get(KEY_BUTTONS)
    key = generate_key()
    msg_id = database.create_message(user_id, key, text, image, buttons)
    if msg_id:
        await query.edit_message_text(
            f"✅ <b>消息已保存！</b>\n\n"
            f"🔑 密钥：<code>{key}</code>\n\n"
            f"💡 在任意聊天中输入 @机器人用户名 {key} 即可发送此消息。",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await query.edit_message_text(
            "❌ 保存失败，请稍后重试。",
            reply_markup=main_menu_keyboard(),
        )
    context.user_data.pop(KEY_TEXT, None)
    context.user_data.pop(KEY_IMAGE, None)
    context.user_data.pop(KEY_BUTTONS, None)
    return ConversationHandler.END


async def ai_rewrite_draft(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """对草稿进行 AI 改写（先保存，再改写）"""
    from handlers.delete import _rewrite_message  # 避免循环导入

    query = update.callback_query
    await query.answer("⏳ 正在 AI 改写...")
    user_id = query.from_user.id
    text = context.user_data.get(KEY_TEXT)
    image = context.user_data.get(KEY_IMAGE)
    buttons = context.user_data.get(KEY_BUTTONS)
    key = generate_key()
    msg_id = database.create_message(user_id, key, text, image, buttons)
    if not msg_id:
        await query.edit_message_text("❌ 保存失败，请稍后重试。", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    # 触发改写
    context.user_data.pop(KEY_TEXT, None)
    context.user_data.pop(KEY_IMAGE, None)
    context.user_data.pop(KEY_BUTTONS, None)
    await _do_rewrite(query, msg_id)
    return ConversationHandler.END


async def _do_rewrite(query, message_id: int) -> None:
    """执行 AI 改写并展示结果"""
    import ai_service
    from utils.keyboards import rewrite_result_keyboard

    msg = database.get_message_by_id(message_id)
    if not msg or not msg.get("text"):
        await query.edit_message_text("❌ 消息不存在或无文本内容", reply_markup=main_menu_keyboard())
        return
    await query.edit_message_text("⏳ AI 改写中，请稍候...")
    variants = ai_service.rewrite_text(msg["text"])
    if not variants:
        await query.edit_message_text("❌ AI 改写失败，请稍后重试。", reply_markup=main_menu_keyboard())
        return
    database.save_variants(message_id, variants)
    import random
    sample = random.choice(variants)
    await query.edit_message_text(
        f"🤖 <b>AI 改写结果（共 {len(variants)} 条变体）</b>\n\n"
        f"随机展示：\n{sample}",
        parse_mode="HTML",
        reply_markup=rewrite_result_keyboard(message_id),
    )


async def restart_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """重新开始创建流程"""
    query = update.callback_query
    await query.answer()
    context.user_data.pop(KEY_TEXT, None)
    context.user_data.pop(KEY_IMAGE, None)
    context.user_data.pop(KEY_BUTTONS, None)
    await query.edit_message_text("✍️ 请发送消息文本内容：")
    return STATE_TEXT


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """取消创建"""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "已取消。", reply_markup=main_menu_keyboard()
        )
    elif update.message:
        await update.message.reply_text("已取消。", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


def create_conversation_handler() -> ConversationHandler:
    """构建创建消息的 ConversationHandler"""
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_create, pattern="^create$")],
        states={
            STATE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text)],
            STATE_IMAGE: [
                CallbackQueryHandler(ask_image_yes, pattern="^add_image_yes$"),
                CallbackQueryHandler(ask_image_no, pattern="^add_image_no$"),
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, receive_image),
            ],
            STATE_BUTTONS: [
                CallbackQueryHandler(ask_buttons_yes, pattern="^add_buttons_yes$"),
                CallbackQueryHandler(ask_buttons_no, pattern="^add_buttons_no$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_buttons),
            ],
            STATE_CONFIRM: [
                CallbackQueryHandler(save_message, pattern="^save$"),
                CallbackQueryHandler(ai_rewrite_draft, pattern="^ai_rewrite$"),
                CallbackQueryHandler(restart_create, pattern="^restart$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern="^cancel$"),
        ],
        allow_reentry=True,
    )
