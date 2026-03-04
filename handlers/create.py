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
import ai_service
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
KEY_IMAGE_FILE_IDS = "draft_image_file_ids"
KEY_BUTTONS = "draft_buttons"


async def start_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """进入创建消息流程"""
    query = update.callback_query
    await query.answer()
    # 清空草稿
    _clear_data(context)
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
    context.user_data.pop(KEY_IMAGE_FILE_IDS, None)
    await query.edit_message_text(
        "🔘 是否添加按钮？",
        reply_markup=yes_no_keyboard("add_buttons_yes", "add_buttons_no"),
    )
    return STATE_BUTTONS


async def receive_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """接收图片并生成10个防检测变体"""
    if update.message.photo:
        file = update.message.photo[-1]
    elif update.message.document and update.message.document.mime_type.startswith("image/"):
        file = update.message.document
    else:
        await update.message.reply_text("❌ 请发送图片文件")
        return STATE_IMAGE

    processing_msg = await update.message.reply_text(
        "⏳ 正在处理图片...\n生成 10 个防检测变体，需要 10-20 秒"
    )

    try:
        file_obj = await context.bot.get_file(file.file_id)
        image_bytes = await file_obj.download_as_bytearray()
    except Exception as e:
        logger.error("下载图片失败: %s", e)
        await processing_msg.edit_text("❌ 图片下载失败，请重新上传")
        return STATE_IMAGE

    from utils.image_processor import generate_image_variants
    image_variant_count = 10
    variants = generate_image_variants(bytes(image_bytes), count=image_variant_count)

    if not variants or len(variants) < image_variant_count:
        await processing_msg.edit_text("❌ 图片处理失败，请重新上传")
        return STATE_IMAGE

    file_ids = []
    for idx, variant_bytes in enumerate(variants):
        try:
            sent = await context.bot.send_photo(
                chat_id=update.effective_user.id,
                photo=variant_bytes,
                caption=f"图片变体 {idx + 1}/{image_variant_count}（此消息将自动删除）",
            )
            file_ids.append(sent.photo[-1].file_id)
            await sent.delete()
        except Exception as e:
            logger.error("上传图片变体 %d 失败: %s", idx + 1, e)

    if len(file_ids) < image_variant_count:
        await processing_msg.edit_text("❌ 部分图片上传失败，请重试")
        return STATE_IMAGE

    context.user_data[KEY_IMAGE_FILE_IDS] = file_ids
    context.user_data[KEY_IMAGE] = f"tg://file_id/{file_ids[0]}"

    await processing_msg.edit_text("✅ 已生成 10 个图片变体！")
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
    file_ids = context.user_data.get(KEY_IMAGE_FILE_IDS)
    buttons_json = context.user_data.get(KEY_BUTTONS)

    preview_lines = ["📋 <b>消息预览</b>\n"]
    preview_lines.append(f"📝 文字：{text[:100]}{'...' if len(text) > 100 else ''}")
    if file_ids:
        preview_lines.append(f"🖼 图片：✅ 已生成 {len(file_ids)} 张变体")
    else:
        preview_lines.append("🖼 图片：❌ 未添加")
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
    file_ids = context.user_data.get(KEY_IMAGE_FILE_IDS, [])
    buttons = context.user_data.get(KEY_BUTTONS)
    key = generate_key()
    msg_id = database.create_message(user_id, key, text, None, buttons)
    if not msg_id:
        await query.edit_message_text(
            "❌ 保存失败，请稍后重试。",
            reply_markup=main_menu_keyboard(),
        )
        _clear_data(context)
        return ConversationHandler.END

    # 保存图片变体
    for idx, file_id in enumerate(file_ids):
        database.save_image_variant(msg_id, file_id, idx)

    # 生成并保存文案变体
    await query.edit_message_text("⏳ 正在生成文案变体...")
    variants = ai_service.generate_text_variants(text, count=10) if text else []
    for variant in variants:
        database.add_message_variant(msg_id, variant)

    await query.edit_message_text(
        f"✅ <b>消息已保存！</b>\n\n"
        f"🔑 密钥：<code>{key}</code>\n"
        f"📝 文案变体：{len(variants)} 条\n"
        f"🖼 图片变体：{len(file_ids)} 张\n\n"
        f"💡 在任意聊天中输入 @机器人用户名 {key} 即可发送此消息。",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )
    _clear_data(context)
    return ConversationHandler.END


async def ai_rewrite_draft(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """对草稿进行 AI 改写（先保存，再改写）"""
    from handlers.delete import _rewrite_message  # 避免循环导入

    query = update.callback_query
    await query.answer("⏳ 正在 AI 改写...")
    user_id = query.from_user.id
    text = context.user_data.get(KEY_TEXT)
    file_ids = context.user_data.get(KEY_IMAGE_FILE_IDS, [])
    buttons = context.user_data.get(KEY_BUTTONS)
    key = generate_key()
    msg_id = database.create_message(user_id, key, text, None, buttons)
    if not msg_id:
        await query.edit_message_text("❌ 保存失败，请稍后重试。", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    for idx, file_id in enumerate(file_ids):
        database.save_image_variant(msg_id, file_id, idx)
    _clear_data(context)
    await _do_rewrite(query, msg_id)
    return ConversationHandler.END


async def _do_rewrite(query, message_id: int) -> None:
    """执行 AI 改写并展示结果"""
    from utils.keyboards import rewrite_result_keyboard

    msg = database.get_message_by_id(message_id)
    if not msg or not msg.get("text"):
        await query.edit_message_text("❌ 消息不存在或无文本内容", reply_markup=main_menu_keyboard())
        return
    await query.edit_message_text("⏳ AI 改写中，请稍候...")
    variants = ai_service.generate_text_variants(msg["text"])
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
    _clear_data(context)
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


def _clear_data(context: ContextTypes.DEFAULT_TYPE) -> None:
    """清空创建草稿数据"""
    context.user_data.pop(KEY_TEXT, None)
    context.user_data.pop(KEY_IMAGE, None)
    context.user_data.pop(KEY_IMAGE_FILE_IDS, None)
    context.user_data.pop(KEY_BUTTONS, None)


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
