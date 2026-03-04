"""数据库操作模块：封装所有数据库操作"""

import sqlite3
import os
import logging
from typing import Optional, List, Dict, Any

from config import DATABASE_PATH

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """初始化数据库，创建表结构"""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                key TEXT UNIQUE NOT NULL,
                text TEXT,
                image_url TEXT,
                buttons TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_user_key ON messages(user_id, key);

            CREATE TABLE IF NOT EXISTS message_variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                variant_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS message_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                file_id TEXT NOT NULL,
                image_index INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_message_images ON message_images(message_id);
        """)
    logger.info("数据库初始化完成")


def create_message(
    user_id: int,
    key: str,
    text: Optional[str] = None,
    image_url: Optional[str] = None,
    buttons: Optional[str] = None,
) -> Optional[int]:
    """创建新消息，返回消息 ID"""
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO messages (user_id, key, text, image_url, buttons)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, key, text, image_url, buttons),
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        logger.warning("消息密钥重复：%s", key)
        return None
    except sqlite3.Error as e:
        logger.error("创建消息失败：%s", e)
        return None


def get_message_by_key(user_id: int, key: str) -> Optional[Dict[str, Any]]:
    """按用户 ID 和密钥查询消息"""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM messages WHERE user_id = ? AND key = ?",
                (user_id, key),
            ).fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logger.error("查询消息失败：%s", e)
        return None


def get_message_by_key_global(key: str) -> Optional[Dict[str, Any]]:
    """全局按密钥查询消息（用于 inline 查询）"""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM messages WHERE key = ?",
                (key,),
            ).fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logger.error("查询消息失败：%s", e)
        return None


def get_message_by_id(message_id: int) -> Optional[Dict[str, Any]]:
    """按 ID 查询消息"""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM messages WHERE id = ?",
                (message_id,),
            ).fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logger.error("查询消息失败：%s", e)
        return None


def get_user_messages(user_id: int, page: int = 1, page_size: int = 5) -> List[Dict[str, Any]]:
    """分页查询用户消息列表"""
    offset = (page - 1) * page_size
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM messages WHERE user_id = ?
                   ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (user_id, page_size, offset),
            ).fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as e:
        logger.error("查询消息列表失败：%s", e)
        return []


def count_user_messages(user_id: int) -> int:
    """统计用户消息总数"""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return row["cnt"] if row else 0
    except sqlite3.Error as e:
        logger.error("统计消息失败：%s", e)
        return 0


def update_message(
    message_id: int,
    text: Optional[str] = None,
    image_url: Optional[str] = None,
    buttons: Optional[str] = None,
) -> bool:
    """更新消息内容"""
    try:
        with get_connection() as conn:
            conn.execute(
                """UPDATE messages
                   SET text = ?, image_url = ?, buttons = ?,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (text, image_url, buttons, message_id),
            )
        return True
    except sqlite3.Error as e:
        logger.error("更新消息失败：%s", e)
        return False


def delete_message(message_id: int) -> bool:
    """删除消息"""
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        return True
    except sqlite3.Error as e:
        logger.error("删除消息失败：%s", e)
        return False


def save_variants(message_id: int, variants: List[str]) -> bool:
    """保存 AI 生成的消息变体（先删除旧变体）"""
    try:
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM message_variants WHERE message_id = ?",
                (message_id,),
            )
            conn.executemany(
                "INSERT INTO message_variants (message_id, variant_text) VALUES (?, ?)",
                [(message_id, v) for v in variants if v.strip()],
            )
        return True
    except sqlite3.Error as e:
        logger.error("保存变体失败：%s", e)
        return False


def get_variants(message_id: int) -> List[str]:
    """获取消息的所有变体"""
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT variant_text FROM message_variants WHERE message_id = ?",
                (message_id,),
            ).fetchall()
            return [row["variant_text"] for row in rows]
    except sqlite3.Error as e:
        logger.error("获取变体失败：%s", e)
        return []


def key_exists(key: str) -> bool:
    """检查密钥是否已存在"""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM messages WHERE key = ?", (key,)
            ).fetchone()
            return row is not None
    except sqlite3.Error as e:
        logger.error("检查密钥失败：%s", e)
        return False


def search_user_messages(user_id: int, query: str) -> List[Dict[str, Any]]:
    """按关键字搜索用户消息（用于 inline 查询）"""
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM messages
                   WHERE user_id = ? AND (key LIKE ? OR text LIKE ?)
                   ORDER BY created_at DESC LIMIT 10""",
                (user_id, f"%{query}%", f"%{query}%"),
            ).fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as e:
        logger.error("搜索消息失败：%s", e)
        return []


def add_message_variant(message_id: int, variant_text: str) -> bool:
    """添加单条消息变体"""
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO message_variants (message_id, variant_text) VALUES (?, ?)",
                (message_id, variant_text),
            )
        return True
    except sqlite3.Error as e:
        logger.error("添加变体失败：%s", e)
        return False


def get_message_variants(message_id: int) -> List[str]:
    """获取消息的所有文案变体（get_variants 的别名）"""
    return get_variants(message_id)


def delete_message_variants(message_id: int) -> bool:
    """删除消息的所有文案变体"""
    try:
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM message_variants WHERE message_id = ?",
                (message_id,),
            )
        return True
    except sqlite3.Error as e:
        logger.error("删除变体失败：%s", e)
        return False


def save_image_variant(message_id: int, file_id: str, image_index: int) -> bool:
    """保存单张图片变体"""
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO message_images (message_id, file_id, image_index) VALUES (?, ?, ?)",
                (message_id, file_id, image_index),
            )
        return True
    except sqlite3.Error as e:
        logger.error("保存图片变体失败：%s", e)
        return False


def get_message_image_variants(message_id: int) -> List[Dict[str, Any]]:
    """获取消息的所有图片变体"""
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT file_id, image_index FROM message_images WHERE message_id = ? ORDER BY image_index",
                (message_id,),
            ).fetchall()
            return [{"file_id": row["file_id"], "index": row["image_index"]} for row in rows]
    except sqlite3.Error as e:
        logger.error("获取图片变体失败：%s", e)
        return []


def get_image_variant_count(message_id: int) -> int:
    """获取图片变体数量"""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM message_images WHERE message_id = ?",
                (message_id,),
            ).fetchone()
            return row["cnt"] if row else 0
    except sqlite3.Error as e:
        logger.error("获取图片数量失败：%s", e)
        return 0
