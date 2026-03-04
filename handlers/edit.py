"""编辑消息处理器（ConversationHandler 流程）"""

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
from utils.keyboards import edit_field_keyboard, main_menu_keyboard
from utils.helpers import format_buttons_input
from utils.validators import validate_message_text, validate_button_input

logger = logging.getLogger(__name__)

# 对话状态
STATE_EDIT_TEXT, STATE_EDIT_IMAGE, STATE_EDIT_BUTTONS = range(3)

KEY_EDIT_ID = "edit_message_id"
KEY_EDIT_FIELD = "edit_field"


async def start_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """进入编辑流程，显示字段选择"""
    query = update.callback_query
    await query.answer()
    message_id = int(query.data.split("_")[1])
    context.user_data[KEY_EDIT_ID] = message_id
    msg = database.get_message_by_id(message_id)
    if not msg:
        await query.edit_message_text("❌ 消息不存在", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    await query.edit_message_text(
        f"✏️ 修改消息（密钥：<code>{msg['key']}</code>）\n\n请选择要修改的内容：",
        parse_mode="HTML",
        reply_markup=edit_field_keyboard(message_id),
    )
    return ConversationHandler.END  # 字段选择由各自回调驱动


async def edit_text_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """开始编辑文字"""
    query = update.callback_query
    await query.answer()
    message_id = int(query.data.split("_")[2])
    context.user_data[KEY_EDIT_ID] = message_id
    await query.edit_message_text("📝 请发送新的消息文字：")
    return STATE_EDIT_TEXT


async def edit_text_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """接收新文字并保存"""
    text = update.message.text
    valid, err = validate_message_text(text)
    if not valid:
        await update.message.reply_text(f"❌ {err}\n请重新发送消息文字：")
        return STATE_EDIT_TEXT
    message_id = context.user_data.get(KEY_EDIT_ID)
    msg = database.get_message_by_id(message_id)
    if not msg:
        await update.message.reply_text("❌ 消息不存在", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    database.update_message(message_id, text=text, image_url=msg.get("image_url"), buttons=msg.get("buttons"))
    await update.message.reply_text(
        "✅ 文字已更新！",
        reply_markup=edit_field_keyboard(message_id),
    )
    return ConversationHandler.END


async def edit_image_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """开始编辑图片"""
    query = update.callback_query
    await query.answer()
    message_id = int(query.data.split("_")[2])
    context.user_data[KEY_EDIT_ID] = message_id
    await query.edit_message_text("🖼 请发送新的图片（或发送「清除」删除图片）：")
    return STATE_EDIT_IMAGE


async def edit_image_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """接收新图片并保存"""
    message_id = context.user_data.get(KEY_EDIT_ID)
    msg = database.get_message_by_id(message_id)
    if not msg:
        await update.message.reply_text("❌ 消息不存在", reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    if update.message.text and update.message.text.strip() == "清除":
        image_url = None
    elif update.message.photo:
        file_id = update.message.photo[-1].file_id
        image_url = f"tg://file_id/{file_id}"
    elif update.message.document and update.message.document.mime_type.startswith("image/"):
        image_url = f"tg://file_id/{update.message.document.file_id}"
    else:
        await update.message.reply_text("❌ 请发送图片，或发送「清除」删除图片")
        return STATE_EDIT_IMAGE

    database.update_message(message_id, text=msg.get("text"), image_url=image_url, buttons=msg.get("buttons"))
    await update.message.reply_text(
        "✅ 图片已更新！",
        reply_markup=edit_field_keyboard(message_id),
    )
    return ConversationHandler.END


async def edit_buttons_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """开始编辑按钮"""
    query = update.callback_query
    await query.answer()
    message_id = int(query.data.split("_")[2])
    context.user_data[KEY_EDIT_ID] = message_id
    await query.edit_message_text(
        "🔘 请按格式输入新的按钮（每行一个），或发送「清除」删除按钮：\n"
        "<code>按钮文字|https://链接</code>",
        parse_mode="HTML",
    )
    return STATE_EDIT_BUTTONS


async def edit_buttons_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """接收新按钮并保存"""
    message_id = context.user_data.get(KEY_EDIT_ID)
    msg = database.get_message_by_id(message_id)
    if not msg:
        await update.message.reply_text("❌ 消息不存在", reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    raw = update.message.text.strip()
    if raw == "清除":
        buttons = None
    else:
        valid, err = validate_button_input(raw)
        if not valid:
            await update.message.reply_text(
                f"❌ {err}\n请重新输入按钮（或发送「清除」删除按钮）："
            )
            return STATE_EDIT_BUTTONS
        buttons = format_buttons_input(raw)

    database.update_message(message_id, text=msg.get("text"), image_url=msg.get("image_url"), buttons=buttons)
    await update.message.reply_text(
        "✅ 按钮已更新！",
        reply_markup=edit_field_keyboard(message_id),
    )
    return ConversationHandler.END


async def cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """取消编辑"""
    message_id = context.user_data.get(KEY_EDIT_ID)
    if update.callback_query:
        await update.callback_query.answer()
        if message_id:
            from utils.keyboards import message_detail_keyboard
            await update.callback_query.edit_message_text(
                "已取消编辑。", reply_markup=message_detail_keyboard(message_id)
            )
        else:
            await update.callback_query.edit_message_text(
                "已取消。", reply_markup=main_menu_keyboard()
            )
    elif update.message:
        await update.message.reply_text("已取消编辑。", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


def edit_conversation_handler() -> ConversationHandler:
    """构建编辑消息的 ConversationHandler"""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(edit_text_start, pattern=r"^edit_text_\d+$"),
            CallbackQueryHandler(edit_image_start, pattern=r"^edit_image_\d+$"),
            CallbackQueryHandler(edit_buttons_start, pattern=r"^edit_buttons_\d+$"),
        ],
        states={
            STATE_EDIT_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_text_receive)
            ],
            STATE_EDIT_IMAGE: [
                MessageHandler(
                    (filters.PHOTO | filters.Document.IMAGE | filters.TEXT) & ~filters.COMMAND,
                    edit_image_receive,
                )
            ],
            STATE_EDIT_BUTTONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_buttons_receive)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_edit),
            CallbackQueryHandler(cancel_edit, pattern="^cancel$"),
        ],
        allow_reentry=True,
    )
