"""删除消息和 AI 改写处理器"""

import logging
import random

from telegram import Update
from telegram.ext import ContextTypes

import database
import ai_service
from utils.keyboards import (
    delete_confirm_keyboard,
    main_menu_keyboard,
    rewrite_result_keyboard,
)

logger = logging.getLogger(__name__)


async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """显示删除确认"""
    query = update.callback_query
    await query.answer()
    message_id = int(query.data.split("_")[1])
    msg = database.get_message_by_id(message_id)
    if not msg:
        await query.edit_message_text("❌ 消息不存在", reply_markup=main_menu_keyboard())
        return
    preview = (msg.get("text") or "（无文本）")[:50]
    await query.edit_message_text(
        f"🗑️ <b>确认删除？</b>\n\n"
        f"🔑 密钥：<code>{msg['key']}</code>\n"
        f"📝 内容：{preview}\n\n"
        f"⚠️ 此操作不可撤销！",
        parse_mode="HTML",
        reply_markup=delete_confirm_keyboard(message_id),
    )


async def confirm_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """执行删除"""
    query = update.callback_query
    await query.answer()
    message_id = int(query.data.split("_")[2])
    ok = database.delete_message(message_id)
    if ok:
        await query.edit_message_text(
            "✅ 消息已删除。",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await query.edit_message_text(
            "❌ 删除失败，请稍后重试。",
            reply_markup=main_menu_keyboard(),
        )


async def rewrite_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 AI 改写回调"""
    query = update.callback_query
    await query.answer("⏳ 正在 AI 改写...")
    message_id = int(query.data.split("_")[1])
    await _rewrite_message(query, message_id)


async def _rewrite_message(query, message_id: int) -> None:
    """执行 AI 改写逻辑"""
    msg = database.get_message_by_id(message_id)
    if not msg or not msg.get("text"):
        await query.edit_message_text(
            "❌ 消息不存在或无文本内容，无法改写。",
            reply_markup=main_menu_keyboard(),
        )
        return
    await query.edit_message_text("⏳ AI 改写中，请稍候...")
    variants = ai_service.rewrite_text(msg["text"])
    if not variants:
        await query.edit_message_text(
            "❌ AI 改写失败，请稍后重试。",
            reply_markup=rewrite_result_keyboard(message_id),
        )
        return
    database.save_variants(message_id, variants)
    sample = random.choice(variants)
    await query.edit_message_text(
        f"🤖 <b>AI 改写完成！</b>\n\n"
        f"共生成 <b>{len(variants)}</b> 条变体，随机展示一条：\n\n"
        f"{sample}",
        parse_mode="HTML",
        reply_markup=rewrite_result_keyboard(message_id),
    )
