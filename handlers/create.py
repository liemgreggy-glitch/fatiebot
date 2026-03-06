"""创建消息处理器（ConversationHandler 流程）"""

import logging
from typing import Optional

from telegram import Update, Message, InlineKeyboardButton, InlineKeyboardMarkup
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
    STATE_GENERATE_VOICE,
    STATE_IMAGE,
    STATE_BUTTONS,
    STATE_CONFIRM,
) = range(5)

# context.user_data 键名
KEY_TEXT = "draft_text"
KEY_TEXT_VARIANTS = "draft_text_variants"
KEY_VOICE_INFOS = "draft_voice_infos"
KEY_IMAGE = "draft_image"
KEY_IMAGE_FILE_IDS = "draft_image_file_ids"
KEY_BUTTONS = "draft_buttons"

# 语音生成最低要求数量
MIN_VOICE_VARIANTS = 3


async def start_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """进入创建消息流程 - 询问是否添加文案"""
    query = update.callback_query
    await query.answer()
    # 清空草稿
    _clear_data(context)
    await query.edit_message_text(
        "📝 <b>创建新消息</b>\n\n是否添加文案？",
        parse_mode="HTML",
        reply_markup=yes_no_keyboard("add_text_yes", "add_text_no"),
    )
    return STATE_TEXT


async def ask_text_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """用户选择添加文案"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✍️ 请发送消息文本内容：")
    return STATE_TEXT


async def ask_text_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """用户选择跳过文案"""
    query = update.callback_query
    await query.answer()
    context.user_data.pop(KEY_TEXT, None)
    await query.edit_message_text(
        "🖼 是否添加图片？",
        reply_markup=yes_no_keyboard("add_image_yes", "add_image_no"),
    )
    return STATE_IMAGE


async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """接收消息文本"""
    text = update.message.text
    valid, err = validate_message_text(text)
    if not valid:
        await update.message.reply_text(f"❌ {err}\n请重新发送消息文本：")
        return STATE_TEXT
    context.user_data[KEY_TEXT] = text

    # 询问是否生成语音
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🎤 生成语音", callback_data="voice_yes"),
                InlineKeyboardButton("⏭️ 跳过", callback_data="voice_no"),
            ]
        ]
    )
    await update.message.reply_text(
        "🎤 <b>是否为文案生成 AI 语音？</b>\n\n"
        "✨ <b>功能说明：</b>\n"
        "• 自动生成 10 条文案变体\n"
        "• 为每条文案生成不同音色的语音\n"
        "• 发送时随机选择，增加多样性\n\n"
        "⏱ <b>预计时间：</b> 30-60 秒\n"
        "💰 <b>费用：</b> 完全免费",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    return STATE_GENERATE_VOICE


async def generate_voice_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """用户选择生成语音"""
    query = update.callback_query
    await query.answer()

    text = context.user_data.get(KEY_TEXT)
    user_id = query.from_user.id

    progress_msg = await query.edit_message_text(
        "⏳ <b>AI 正在生成...</b>\n\n"
        "📝 生成文案变体... ⏳\n"
        "🎤 生成语音变体... 等待中",
        parse_mode="HTML",
    )

    # 生成文案变体
    text_variants = ai_service.generate_text_variants(text, count=10)

    if not text_variants or len(text_variants) < MIN_VOICE_VARIANTS:
        await progress_msg.edit_text(
            "❌ 文案生成失败，已跳过语音生成",
            reply_markup=yes_no_keyboard("add_image_yes", "add_image_no"),
        )
        return STATE_IMAGE

    # 更新进度
    await progress_msg.edit_text(
        "⏳ <b>AI 正在生成...</b>\n\n"
        f"📝 生成文案变体... ✅ ({len(text_variants)} 条)\n"
        "🎤 生成语音变体... 0/10",
        parse_mode="HTML",
    )

    # 定义进度回调
    async def update_progress(current, total):
        try:
            await progress_msg.edit_text(
                "⏳ <b>AI 正在生成...</b>\n\n"
                f"📝 生成文案变体... ✅ ({len(text_variants)} 条)\n"
                f"🎤 生成语音变体... {current}/{total}",
                parse_mode="HTML",
            )
        except Exception:
            pass

    # 生成并上传语音
    from utils.voice_processor import generate_and_upload_voices

    voice_infos = await generate_and_upload_voices(
        context.bot,
        user_id,
        text_variants,
        progress_callback=update_progress,
    )

    if not voice_infos or len(voice_infos) < MIN_VOICE_VARIANTS:
        await progress_msg.edit_text(
            "❌ 语音生成失败，请检查网络后重试\n\n🖼 是否继续添加图片？",
            reply_markup=yes_no_keyboard("add_image_yes", "add_image_no"),
        )
        return STATE_IMAGE

    # 保存到 context
    context.user_data[KEY_TEXT_VARIANTS] = text_variants
    context.user_data[KEY_VOICE_INFOS] = voice_infos

    # 成功提示
    await progress_msg.edit_text(
        f"✅ <b>生成完成！</b>\n\n"
        f"📝 文案变体：{len(text_variants)} 条\n"
        f"🎤 语音变体：{len(voice_infos)} 条\n\n"
        f"💡 <b>示例文案：</b>\n{text_variants[0][:80]}...",
        parse_mode="HTML",
    )

    # 发送试听语音
    await context.bot.send_voice(
        chat_id=user_id,
        voice=voice_infos[0]["file_id"],
        caption=f"🎧 <b>试听：语音变体 #1</b>\n\n{text_variants[0][:200]}",
        parse_mode="HTML",
    )

    # 继续流程：询问是否添加图片
    await context.bot.send_message(
        chat_id=user_id,
        text="🖼 是否添加图片？",
        reply_markup=yes_no_keyboard("add_image_yes", "add_image_no"),
    )
    return STATE_IMAGE


async def generate_voice_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """用户选择跳过语音"""
    query = update.callback_query
    await query.answer()

    context.user_data.pop(KEY_VOICE_INFOS, None)
    context.user_data.pop(KEY_TEXT_VARIANTS, None)

    await query.edit_message_text(
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
    text = context.user_data.get(KEY_TEXT)
    file_ids = context.user_data.get(KEY_IMAGE_FILE_IDS)
    buttons_json = context.user_data.get(KEY_BUTTONS)

    # 验证：至少有一项内容
    if not (text or file_ids or buttons_json):
        error_msg = "❌ 至少需要添加文案、图片或按钮之一\n\n请重新开始创建"
        if hasattr(msg_or_query, "edit_message_text"):
            await msg_or_query.edit_message_text(error_msg, reply_markup=main_menu_keyboard())
        else:
            await msg_or_query.reply_text(error_msg, reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    preview_lines = ["📋 <b>消息预览</b>\n"]
    if text:
        preview_lines.append(f"📝 文字：{text[:100]}{'...' if len(text) > 100 else ''}")
    else:
        preview_lines.append("📝 文字：（无）")
    if file_ids:
        preview_lines.append(f"🖼 图片：✅ 已生成 {len(file_ids)} 张变体")
    else:
        preview_lines.append("🖼 图片：（无）")
    preview_lines.append(f"🔘 按钮：{'✅ 已添加' if buttons_json else '（无）'}")

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
    text_variants = context.user_data.get(KEY_TEXT_VARIANTS, [])
    voice_infos = context.user_data.get(KEY_VOICE_INFOS, [])
    file_ids = context.user_data.get(KEY_IMAGE_FILE_IDS, [])
    buttons = context.user_data.get(KEY_BUTTONS)

    # 再次验证：至少有一项内容
    if not (text or file_ids or buttons):
        await query.edit_message_text(
            "❌ 至少需要添加文案、图片或按钮之一",
            reply_markup=main_menu_keyboard(),
        )
        _clear_data(context)
        return ConversationHandler.END

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

    # 保存文案变体：优先使用已生成的，否则现在生成
    if text_variants:
        for variant in text_variants:
            database.add_message_variant(msg_id, variant)
        variants = text_variants
    elif text:
        await query.edit_message_text("⏳ 正在生成文案变体...")
        variants = ai_service.generate_text_variants(text, count=10)
        for variant in variants:
            database.add_message_variant(msg_id, variant)
    else:
        variants = []

    # 保存语音变体
    for info in voice_infos:
        database.save_voice_variant(
            msg_id, info["file_id"], info["index"], info.get("duration", 0)
        )

    await query.edit_message_text(
        f"✅ <b>消息已保存！</b>\n\n"
        f"🔑 密钥：<code>{key}</code>\n"
        f"📝 文案变体：{len(variants)} 条\n"
        f"🎤 语音变体：{len(voice_infos)} 条\n"
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
    await query.edit_message_text(
        "📝 <b>创建新消息</b>\n\n是否添加文案？",
        parse_mode="HTML",
        reply_markup=yes_no_keyboard("add_text_yes", "add_text_no"),
    )
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
    context.user_data.pop(KEY_TEXT_VARIANTS, None)
    context.user_data.pop(KEY_VOICE_INFOS, None)
    context.user_data.pop(KEY_IMAGE, None)
    context.user_data.pop(KEY_IMAGE_FILE_IDS, None)
    context.user_data.pop(KEY_BUTTONS, None)


def create_conversation_handler() -> ConversationHandler:
    """构建创建消息的 ConversationHandler"""
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_create, pattern="^create$")],
        states={
            STATE_TEXT: [
                CallbackQueryHandler(ask_text_yes, pattern="^add_text_yes$"),
                CallbackQueryHandler(ask_text_no, pattern="^add_text_no$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text),
            ],
            STATE_GENERATE_VOICE: [
                CallbackQueryHandler(generate_voice_yes, pattern="^voice_yes$"),
                CallbackQueryHandler(generate_voice_no, pattern="^voice_no$"),
            ],
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
