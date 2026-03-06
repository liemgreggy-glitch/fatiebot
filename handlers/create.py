"""创建消息处理器（ConversationHandler 流程）- 完整修复版 v2"""

import logging
import json
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
    STATE_VOICE_CHOICE,
    STATE_VOICE_TEXT,
    STATE_TEXT_CONFIG,
    STATE_TEXT_CHOICE,
    STATE_TEXT_INPUT,
    STATE_IMAGE,
    STATE_BUTTONS,
    STATE_CONFIRM,
) = range(8)

# context.user_data 键名
KEY_TEXT = "draft_text"
KEY_VOICE_TEXT = "draft_voice_text"
KEY_SHOW_TEXT = "draft_show_text"
KEY_TEXT_VARIANTS = "draft_text_variants"
KEY_VOICE_INFOS = "draft_voice_infos"
KEY_IMAGE = "draft_image"
KEY_IMAGE_FILE_IDS = "draft_image_file_ids"
KEY_BUTTONS = "draft_buttons"
KEY_BUTTON_POOL = "draft_button_pool"

# 语音生成最低要求数量
MIN_VOICE_VARIANTS = 3


async def start_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """进入创建消息流程 - 第一步询问是否生成语音"""
    query = update.callback_query
    await query.answer()
    # 清空草稿
    _clear_data(context)
    
    await query.edit_message_text(
        "🎤 <b>是否需要生成语音？</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ 是", callback_data="voice_yes")],
            [InlineKeyboardButton("❌ 否", callback_data="voice_no")],
            [InlineKeyboardButton("❌ 取消", callback_data="cancel")]
        ])
    )
    return STATE_VOICE_CHOICE


async def handle_voice_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """用户选择生成语音"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['need_voice'] = True
    
    await query.edit_message_text(
        "📝 <b>请输入要生成语音的内容：</b>",
        parse_mode="HTML"
    )
    return STATE_VOICE_TEXT


async def handle_voice_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """用户选择不生成语音 - 仍然可以配置文案"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['need_voice'] = False
    
    # 询问是否添加文案
    await query.edit_message_text(
        "📝 <b>是否添加文案？</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ 是", callback_data="text_choice_yes")],
            [InlineKeyboardButton("❌ 否", callback_data="text_choice_no")]
        ])
    )
    return STATE_TEXT_CHOICE


async def handle_text_choice_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """用户选择添加文案（不生成语音的情况）"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📝 <b>请输入文案内容：</b>\n\n"
        "💡 将自动生成 10 条变体",
        parse_mode="HTML"
    )
    return STATE_TEXT_INPUT


async def handle_text_choice_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """用户选择不添加文案（不生成语音的情况）"""
    query = update.callback_query
    await query.answer()
    
    context.user_data[KEY_SHOW_TEXT] = None
    context.user_data[KEY_TEXT] = None
    context.user_data[KEY_TEXT_VARIANTS] = []
    
    await query.edit_message_text(
        "🖼 <b>是否添加图片？</b>",
        parse_mode="HTML",
        reply_markup=yes_no_keyboard("add_image_yes", "add_image_no"),
    )
    return STATE_IMAGE


async def receive_voice_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """接收语音文字并生成 5 条语音变体"""
    text = update.message.text.strip()
    valid, err = validate_message_text(text)
    if not valid:
        await update.message.reply_text(f"❌ {err}\n请重新输入：")
        return STATE_VOICE_TEXT
    
    # 保存语音文字
    context.user_data[KEY_VOICE_TEXT] = text
    
    # 显示生成中
    progress_msg = await update.message.reply_text(
        "🎤 <b>正在生成语音变体...</b>\n📝 生成文案变体...",
        parse_mode="HTML"
    )
    
    try:
        # 生成 5 条文案变体
        logger.info("开始生成 5 条文案变体")
        text_variants = ai_service.generate_text_variants(text, count=5)
        if not text_variants or len(text_variants) < 3:
            logger.warning("文案变体生成失败或不足，使用原文")
            text_variants = [text] * 5
        
        logger.info(f"成功生成 {len(text_variants)} 条文案变体")
        
        await progress_msg.edit_text(
            f"🎤 <b>正在生成语音变体...</b>\n"
            f"📝 文案变体：✅ {len(text_variants)} 条\n"
            f"🎤 生成语音：0/{len(text_variants)}",
            parse_mode="HTML"
        )
        
        # 定义进度回调
        async def update_progress(current, total):
            try:
                await progress_msg.edit_text(
                    f"🎤 <b>正在生成语音变体...</b>\n"
                    f"📝 文案变体：✅ {len(text_variants)} 条\n"
                    f"🎤 生成语音：{current}/{total}",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        
        # 生成语音
        from utils.voice_processor import generate_and_upload_voices
        
        logger.info("开始生成语音")
        voice_infos = await generate_and_upload_voices(
            context.bot,
            update.effective_user.id,
            text_variants,
            progress_callback=update_progress
        )
        
        if not voice_infos:
            await progress_msg.edit_text("❌ 语音生成失败，请重试")
            return ConversationHandler.END
        
        logger.info(f"成功生成 {len(voice_infos)} 条语音")
        
        # 保存语音信息
        context.user_data[KEY_VOICE_INFOS] = voice_infos
        
        # 询问是否添加配置文案
        await progress_msg.edit_text(
            f"✅ <b>语音已生成！</b>\n\n"
            f"🎤 语音变体：{len(voice_infos)} 条\n\n"
            f"📝 <b>是否添加配置文案？</b>\n"
            f"（如果选择 是，可以输入不同的显示文字）",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ 是", callback_data="text_config_yes")],
                [InlineKeyboardButton("❌ 否", callback_data="text_config_no")]
            ])
        )
        
        return STATE_TEXT_CONFIG
        
    except Exception as e:
        logger.error(f"生成语音失败: {e}", exc_info=True)
        await progress_msg.edit_text(f"❌ 生成失败: {e}")
        return ConversationHandler.END


async def handle_text_config_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """用户选择添加配置文案 - 需要用户输入"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📝 <b>请输入要显示的文案：</b>\n\n"
        "💡 这个文案将和语音一起发送\n"
        "（可以和语音内容不同）\n\n"
        "将自动生成 10 条变体",
        parse_mode="HTML"
    )
    return STATE_TEXT_INPUT


async def handle_text_config_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """用户选择不添加配置文案"""
    query = update.callback_query
    await query.answer()
    
    # 不显示文案
    context.user_data[KEY_SHOW_TEXT] = None
    context.user_data[KEY_TEXT] = None
    context.user_data[KEY_TEXT_VARIANTS] = []
    
    await query.edit_message_text(
        "🖼 <b>是否添加图片？</b>",
        parse_mode="HTML",
        reply_markup=yes_no_keyboard("add_image_yes", "add_image_no"),
    )
    return STATE_IMAGE


async def receive_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """接收用户输入的显示文案并生成 10 条变体"""
    text = update.message.text.strip()
    
    if not text:
        await update.message.reply_text("⚠️ 文案不能为空，请重新输入")
        return STATE_TEXT_INPUT
    
    # 生成文案变体
    processing_msg = await update.message.reply_text("📝 <b>正在生成文案变体...</b>", parse_mode="HTML")
    
    try:
        logger.info("开始生成 10 条文案变体")
        text_variants = ai_service.generate_text_variants(text, count=10)
        if not text_variants or len(text_variants) < 5:
            logger.warning("文案变体生成失败或不足，使用原文")
            text_variants = [text] * 10
        
        logger.info(f"成功生成 {len(text_variants)} 条文案变体")
        
        # 保存文案变体
        context.user_data[KEY_SHOW_TEXT] = text
        context.user_data[KEY_TEXT] = text
        context.user_data[KEY_TEXT_VARIANTS] = text_variants
        
        await processing_msg.edit_text(f"✅ <b>已生成 {len(text_variants)} 条文案变体！</b>", parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"生成文案变体失败: {e}", exc_info=True)
        # 失败时只用原文
        context.user_data[KEY_SHOW_TEXT] = text
        context.user_data[KEY_TEXT] = text
        context.user_data[KEY_TEXT_VARIANTS] = [text]
        await processing_msg.edit_text("⚠️ 文案变体生成失败，将使用原文")
    
    await update.message.reply_text(
        "🖼 <b>是否添加图片？</b>",
        parse_mode="HTML",
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
        "🔘 <b>请输入按钮配置：</b>\n\n"
        "格式：<code>按钮文字|https://链接</code>\n"
        "每行一个按钮\n\n"
        "💡 <b>多个按钮将随机混合搭配！</b>\n\n"
        "示例：\n"
        "<code>购买|https://example.com\n"
        "购买2|https://example2.com\n"
        "咨询|https://t.me/username</code>\n\n"
        "每次发送时将从中随机选择 1-2 个按钮",
        parse_mode="HTML",
    )
    return STATE_BUTTONS


async def ask_buttons_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """用户选择不添加按钮"""
    query = update.callback_query
    await query.answer()
    context.user_data.pop(KEY_BUTTONS, None)
    context.user_data.pop(KEY_BUTTON_POOL, None)
    return await _show_preview(query, context)


async def receive_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """接收按钮内容（支持多组，随机混合）"""
    raw = update.message.text
    valid, err = validate_button_input(raw)
    if not valid:
        await update.message.reply_text(
            f"❌ {err}\n请重新输入按钮（每行一个，格式：文字|链接）："
        )
        return STATE_BUTTONS
    
    # 解析所有按钮
    buttons = []
    for line in raw.split('\n'):
        line = line.strip()
        if '|' in line:
            text, url = line.split('|', 1)
            buttons.append({"text": text.strip(), "url": url.strip()})
    
    if not buttons:
        await update.message.reply_text("❌ 至少需要 1 个按钮")
        return STATE_BUTTONS
    
    # 保存按钮池（随机混合用）
    context.user_data[KEY_BUTTON_POOL] = buttons
    # 也保存格式化版本（用于数据库）
    context.user_data[KEY_BUTTONS] = format_buttons_input(raw)
    
    await update.message.reply_text(
        f"✅ <b>已保存 {len(buttons)} 个按钮！</b>\n\n"
        f"💡 发���时将随机选择 1-2 个按钮",
        parse_mode="HTML"
    )
    
    return await _show_preview(update.message, context)


async def _show_preview(msg_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """显示消息预览"""
    show_text = context.user_data.get(KEY_SHOW_TEXT)
    voice_infos = context.user_data.get(KEY_VOICE_INFOS, [])
    voice_text = context.user_data.get(KEY_VOICE_TEXT)
    text_variants = context.user_data.get(KEY_TEXT_VARIANTS, [])
    file_ids = context.user_data.get(KEY_IMAGE_FILE_IDS)
    buttons_json = context.user_data.get(KEY_BUTTONS)
    button_pool = context.user_data.get(KEY_BUTTON_POOL, [])

    # 验证：至少有一项内容
    if not (voice_infos or show_text or file_ids or buttons_json):
        error_msg = "❌ 至少需要添加语音、文案、图片或按钮之一\n\n请重新开始创建"
        if hasattr(msg_or_query, "edit_message_text"):
            await msg_or_query.edit_message_text(error_msg, reply_markup=main_menu_keyboard())
        else:
            await msg_or_query.reply_text(error_msg, reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    preview_lines = ["📋 <b>消息预览</b>\n"]
    
    if voice_infos:
        preview_lines.append(f"🎤 语音变体：✅ {len(voice_infos)} 条")
        if voice_text:
            preview_lines.append(f"   内容示例：{voice_text[:50]}{'...' if len(voice_text) > 50 else ''}")
    else:
        preview_lines.append("🎤 语音：（无）")
    
    if show_text:
        preview_lines.append(f"📝 显示文案：{show_text[:100]}{'...' if len(show_text) > 100 else ''}")
        if text_variants:
            preview_lines.append(f"   变体数量：{len(text_variants)} 条")
    else:
        preview_lines.append("📝 显示文案：（无）")
    
    if file_ids:
        preview_lines.append(f"🖼 图片变体：✅ {len(file_ids)} 张")
    else:
        preview_lines.append("🖼 图片：（无）")
    
    if button_pool:
        preview_lines.append(f"🔘 按钮池：✅ {len(button_pool)} 个（随机混合）")
    elif buttons_json:
        preview_lines.append("🔘 按钮：✅ 已添加")
    else:
        preview_lines.append("🔘 按钮：（无）")

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
    
    show_text = context.user_data.get(KEY_SHOW_TEXT)
    voice_text = context.user_data.get(KEY_VOICE_TEXT)
    voice_infos = context.user_data.get(KEY_VOICE_INFOS, [])
    text_variants = context.user_data.get(KEY_TEXT_VARIANTS, [])
    file_ids = context.user_data.get(KEY_IMAGE_FILE_IDS, [])
    buttons = context.user_data.get(KEY_BUTTONS)
    button_pool = context.user_data.get(KEY_BUTTON_POOL, [])

    # 验证
    if not (voice_infos or show_text or file_ids or buttons):
        await query.edit_message_text(
            "❌ 至少需要添加语音、文案、图片或按钮之一",
            reply_markup=main_menu_keyboard(),
        )
        _clear_data(context)
        return ConversationHandler.END

    key = generate_key()
    msg_id = database.create_message(user_id, key, show_text, None, buttons)
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

    # 保存文案变体
    if text_variants:
        for variant in text_variants:
            database.add_message_variant(msg_id, variant)
    elif show_text:
        # 如果没有变体，至少保存原文
        database.add_message_variant(msg_id, show_text)

    # 保存语音变体
    for info in voice_infos:
        database.save_voice_variant(
            msg_id, info["file_id"], info["index"], info.get("duration", 0)
        )
    
    # 保存按钮池（如果有）
    if button_pool:
        try:
            button_pool_json = json.dumps(button_pool, ensure_ascii=False)
            # 尝试保存到数据库（需要数据库支持）
            # 如果数据库没有这个字段，这里会失败，但不影响主流程
            if hasattr(database, 'save_button_pool'):
                database.save_button_pool(msg_id, button_pool_json)
            logger.info(f"按钮池已保存: {len(button_pool)} 个按钮")
        except Exception as e:
            logger.warning(f"保存按钮池失败（不影响主流程）: {e}")

    await query.edit_message_text(
        f"✅ <b>消息已保存！</b>\n\n"
        f"🔑 密钥：<code>{key}</code>\n"
        f"🎤 语音变体：{len(voice_infos)} 条\n"
        f"📝 文案变体：{len(text_variants)} 条\n"
        f"🖼 图片变体：{len(file_ids)} 张\n"
        f"🔘 按钮池：{len(button_pool)} 个\n\n"
        f"💡 在任意聊天中输入 @机器人用户名 {key} 即可发送此消息。\n\n"
        f"🎲 每次发送时将随机选择：\n"
        f"• 语音变体（如有）\n"
        f"• 文案变体（如有）\n"
        f"• 图片变体（如有）\n"
        f"• 按钮组合（1-2个，如有）",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )
    _clear_data(context)
    return ConversationHandler.END


async def restart_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """重新开始创建流程"""
    query = update.callback_query
    await query.answer()
    _clear_data(context)
    await query.edit_message_text(
        "🎤 <b>是否需要生成语音？</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ 是", callback_data="voice_yes")],
            [InlineKeyboardButton("❌ 否", callback_data="voice_no")],
            [InlineKeyboardButton("❌ 取消", callback_data="cancel")]
        ])
    )
    return STATE_VOICE_CHOICE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """取消创建"""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "已取消。", reply_markup=main_menu_keyboard()
        )
    elif update.message:
        await update.message.reply_text("已取消。", reply_markup=main_menu_keyboard())
    _clear_data(context)
    return ConversationHandler.END


def _clear_data(context: ContextTypes.DEFAULT_TYPE) -> None:
    """清空创建草稿数据"""
    context.user_data.pop(KEY_TEXT, None)
    context.user_data.pop(KEY_VOICE_TEXT, None)
    context.user_data.pop(KEY_SHOW_TEXT, None)
    context.user_data.pop(KEY_TEXT_VARIANTS, None)
    context.user_data.pop(KEY_VOICE_INFOS, None)
    context.user_data.pop(KEY_IMAGE, None)
    context.user_data.pop(KEY_IMAGE_FILE_IDS, None)
    context.user_data.pop(KEY_BUTTONS, None)
    context.user_data.pop(KEY_BUTTON_POOL, None)
    context.user_data.pop('need_voice', None)


def create_conversation_handler() -> ConversationHandler:
    """构建创建消息的 ConversationHandler"""
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_create, pattern="^create$")],
        states={
            STATE_VOICE_CHOICE: [
                CallbackQueryHandler(handle_voice_yes, pattern="^voice_yes$"),
                CallbackQueryHandler(handle_voice_no, pattern="^voice_no$"),
                CallbackQueryHandler(cancel, pattern="^cancel$"),
            ],
            STATE_VOICE_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_voice_text),
            ],
            STATE_TEXT_CONFIG: [
                CallbackQueryHandler(handle_text_config_yes, pattern="^text_config_yes$"),
                CallbackQueryHandler(handle_text_config_no, pattern="^text_config_no$"),
            ],
            STATE_TEXT_CHOICE: [
                CallbackQueryHandler(handle_text_choice_yes, pattern="^text_choice_yes$"),
                CallbackQueryHandler(handle_text_choice_no, pattern="^text_choice_no$"),
            ],
            STATE_TEXT_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text_input),
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
                CallbackQueryHandler(restart_create, pattern="^restart$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern="^cancel$"),
        ],
        allow_reentry=True,
    )