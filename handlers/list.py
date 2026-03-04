"""消息列表处理器"""

import logging

from telegram import Update, CallbackQuery
from telegram.ext import ContextTypes

import database
from config import PAGE_SIZE
from utils.keyboards import (
    message_list_keyboard,
    message_detail_keyboard,
    main_menu_keyboard,
)
from utils.helpers import parse_buttons

logger = logging.getLogger(__name__)


async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1) -> None:
    """展示消息列表"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    messages = database.get_user_messages(user_id, page=page, page_size=PAGE_SIZE)
    total = database.count_user_messages(user_id)

    if not messages:
        await query.edit_message_text(
            "📋 你还没有创建任何消息。\n点击下方按钮创建第一条消息！",
            reply_markup=main_menu_keyboard(),
        )
        return

    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    text = f"📋 <b>我的消息</b>（第 {page}/{total_pages} 页，共 {total} 条）\n\n点击消息查看详情："
    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=message_list_keyboard(messages, page, total, PAGE_SIZE),
    )


async def list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 list 回调"""
    await show_list(update, context, page=1)


async def list_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理分页回调"""
    query = update.callback_query
    data = query.data  # list_page_{page}
    page = int(data.split("_")[-1])
    await show_list(update, context, page=page)


def _build_message_detail_text(msg: dict, variants: list) -> str:
    """构建消息详情文本"""
    lines = [f"🔑 <b>密钥</b>：<code>{msg['key']}</code>"]
    if msg.get("text"):
        lines.append(f"\n📝 <b>文字</b>：\n{msg['text']}")
    if msg.get("image_url"):
        lines.append(f"\n🖼 <b>图片</b>：已添加")
    if msg.get("buttons"):
        lines.append(f"\n🔘 <b>按钮</b>：已添加")
    lines.append(f"\n🕐 <b>创建时间</b>：{msg['created_at'][:19]}")
    if variants:
        lines.append(f"\n🤖 <b>AI 变体</b>：{len(variants)} 条")
    return "\n".join(lines)


async def show_message_detail(query: CallbackQuery, message_id: int) -> None:
    """展示消息详情（供其他处理器复用）"""
    msg = database.get_message_by_id(message_id)
    if not msg:
        await query.edit_message_text("❌ 消息不存在", reply_markup=main_menu_keyboard())
        return
    variants = database.get_variants(message_id)
    await query.edit_message_text(
        _build_message_detail_text(msg, variants),
        parse_mode="HTML",
        reply_markup=message_detail_keyboard(message_id),
    )


async def view_message_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """查看消息详情"""
    query = update.callback_query
    await query.answer()
    message_id = int(query.data.split("_")[1])
    await show_message_detail(query, message_id)
