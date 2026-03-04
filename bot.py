"""主程序入口：初始化并启动 Telegram 机器人"""

import logging
import sys

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
)

import config
import database
from handlers.start import start, help_command, main_menu_callback, help_callback
from handlers.create import create_conversation_handler
from handlers.ai_create import ai_create_conversation_handler
from handlers.list import list_callback, list_page_callback, view_message_callback
from handlers.edit import start_edit, edit_conversation_handler
from handlers.delete import delete_callback, confirm_delete_callback, rewrite_callback
from handlers.inline import inline_query

logger = logging.getLogger(__name__)


def main() -> None:
    """启动机器人"""
    config.setup_logging()

    if not config.BOT_TOKEN:
        logger.error("未设置 TELEGRAM_BOT_TOKEN，请在 .env 文件中配置")
        sys.exit(1)

    # 初始化数据库
    database.init_db()

    # 创建 Application
    app = Application.builder().token(config.BOT_TOKEN).build()

    # --- 注册 ConversationHandlers（优先级最高，先注册）---
    app.add_handler(create_conversation_handler())
    app.add_handler(ai_create_conversation_handler())
    app.add_handler(edit_conversation_handler())

    # --- 注册命令处理器 ---
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    # --- 注册回调处理器 ---
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(help_callback, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(list_callback, pattern="^list$"))
    app.add_handler(CallbackQueryHandler(list_page_callback, pattern=r"^list_page_\d+$"))
    app.add_handler(CallbackQueryHandler(view_message_callback, pattern=r"^view_\d+$"))
    app.add_handler(CallbackQueryHandler(start_edit, pattern=r"^edit_\d+$"))
    app.add_handler(CallbackQueryHandler(delete_callback, pattern=r"^delete_\d+$"))
    app.add_handler(CallbackQueryHandler(confirm_delete_callback, pattern=r"^confirm_delete_\d+$"))
    app.add_handler(CallbackQueryHandler(rewrite_callback, pattern=r"^rewrite_\d+$"))

    # --- 注册 Inline 查询处理器 ---
    app.add_handler(InlineQueryHandler(inline_query))

    logger.info("机器人启动成功，开始轮询...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
