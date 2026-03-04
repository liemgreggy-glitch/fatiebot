"""启动和主菜单处理器"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from utils.keyboards import main_menu_keyboard

logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "🏠 欢迎使用消息模板机器人！\n\n"
    "你可以：\n"
    "• ➕ 创建消息模板，自动生成内联密钥\n"
    "• 🚀 在任意聊天输入 @机器人用户名 密钥 一键发送\n"
    "• 🤖 使用 AI 改写去同质化，生成最多 10 条变体\n"
    "• 🎨 使用 AI 创建，自动生成宣传文案+图片\n\n"
    "请选择操作："
)

HELP_TEXT = (
    "❓ <b>使用帮助</b>\n\n"
    "<b>➕ 创建新消息</b>\n"
    "手动填写文字、图片、按钮，系统自动生成唯一密钥。\n\n"
    "<b>🤖 AI 创建</b>\n"
    "输入产品/服务描述，AI 自动生成宣传文案和配图。\n\n"
    "<b>📋 我的消息</b>\n"
    "查看所有已创建的消息，支持编辑、删除、AI 改写。\n\n"
    "<b>🚀 Inline 模式</b>\n"
    "在任意聊天输入框输入：<code>@你的机器人用户名 密钥</code>\n"
    "机器人会显示预览卡片，点击即可发送。\n\n"
    "<b>🤖 AI 改写</b>\n"
    "对已创建的消息，自动生成最多 10 条保留原意的变体。\n"
    "每次 Inline 调用时随机展示一条变体。"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /start 命令"""
    await update.message.reply_text(
        WELCOME_TEXT,
        reply_markup=main_menu_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /help 命令"""
    await update.message.reply_text(
        HELP_TEXT,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理主菜单回调"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        WELCOME_TEXT,
        reply_markup=main_menu_keyboard(),
    )


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理帮助菜单回调"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        HELP_TEXT,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )
