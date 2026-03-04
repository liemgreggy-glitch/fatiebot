"""键盘布局模块：定义机器人的各种键盘"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """主菜单内联键盘"""
    keyboard = [
        [
            InlineKeyboardButton("➕ 创建新消息", callback_data="create"),
            InlineKeyboardButton("🤖 AI 创建", callback_data="ai_create"),
        ],
        [
            InlineKeyboardButton("📋 我的消息", callback_data="list"),
            InlineKeyboardButton("❓ 使用帮助", callback_data="help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def create_confirm_keyboard() -> InlineKeyboardMarkup:
    """创建消息确认键盘"""
    keyboard = [
        [
            InlineKeyboardButton("💾 保存", callback_data="save"),
            InlineKeyboardButton("🤖 AI 改写", callback_data="ai_rewrite"),
        ],
        [InlineKeyboardButton("🔄 重新开始", callback_data="restart")],
    ]
    return InlineKeyboardMarkup(keyboard)


def yes_no_keyboard(yes_data: str, no_data: str) -> InlineKeyboardMarkup:
    """是/否选择键盘"""
    keyboard = [
        [
            InlineKeyboardButton("✅ 是", callback_data=yes_data),
            InlineKeyboardButton("❌ 否", callback_data=no_data),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def back_keyboard() -> InlineKeyboardMarkup:
    """返回主菜单键盘"""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🏠 返回主菜单", callback_data="main_menu")]]
    )


def message_list_keyboard(messages: list, page: int, total: int, page_size: int) -> InlineKeyboardMarkup:
    """消息列表键盘（带分页）"""
    keyboard = []
    for msg in messages:
        preview = (msg["text"] or "（无文本）")[:30]
        keyboard.append(
            [InlineKeyboardButton(
                f"🔑 {msg['key']} | {preview}",
                callback_data=f"view_{msg['id']}",
            )]
        )
    # 分页按钮
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f"list_page_{page - 1}"))
    total_pages = (total + page_size - 1) // page_size
    if page < total_pages:
        nav.append(InlineKeyboardButton("➡️ 下一页", callback_data=f"list_page_{page + 1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("🏠 返回主菜单", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def message_detail_keyboard(message_id: int) -> InlineKeyboardMarkup:
    """消息详情操作键盘"""
    keyboard = [
        [
            InlineKeyboardButton("✏️ 修改", callback_data=f"edit_{message_id}"),
            InlineKeyboardButton("🗑️ 删除", callback_data=f"delete_{message_id}"),
        ],
        [InlineKeyboardButton("🤖 AI 改写", callback_data=f"rewrite_{message_id}")],
        [InlineKeyboardButton("⬅️ 返回列表", callback_data="list")],
    ]
    return InlineKeyboardMarkup(keyboard)


def delete_confirm_keyboard(message_id: int) -> InlineKeyboardMarkup:
    """删除确认键盘"""
    keyboard = [
        [
            InlineKeyboardButton("✅ 确认删除", callback_data=f"confirm_delete_{message_id}"),
            InlineKeyboardButton("❌ 取消", callback_data=f"view_{message_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def edit_field_keyboard(message_id: int) -> InlineKeyboardMarkup:
    """编辑消息字段选择键盘"""
    keyboard = [
        [
            InlineKeyboardButton("📝 修改文字", callback_data=f"edit_text_{message_id}"),
            InlineKeyboardButton("🖼 修改图片", callback_data=f"edit_image_{message_id}"),
        ],
        [InlineKeyboardButton("🔘 修改按钮", callback_data=f"edit_buttons_{message_id}")],
        [InlineKeyboardButton("⬅️ 返回", callback_data=f"view_{message_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)


def ai_create_confirm_keyboard() -> InlineKeyboardMarkup:
    """AI 创建结果确认键盘"""
    keyboard = [
        [
            InlineKeyboardButton("💾 保存", callback_data="ai_save"),
            InlineKeyboardButton("🔄 重新生成", callback_data="ai_regenerate"),
        ],
        [InlineKeyboardButton("❌ 取消", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def rewrite_result_keyboard(message_id: int) -> InlineKeyboardMarkup:
    """AI 改写结果操作键盘"""
    keyboard = [
        [
            InlineKeyboardButton("🔄 再次改写", callback_data=f"rewrite_{message_id}"),
            InlineKeyboardButton("⬅️ 返回", callback_data=f"view_{message_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
