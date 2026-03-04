"""消息模型"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Message:
    """消息数据模型"""
    id: int
    user_id: int
    key: str
    text: Optional[str]
    image_url: Optional[str]
    buttons: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """从字典构造消息对象"""
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            key=data["key"],
            text=data.get("text"),
            image_url=data.get("image_url"),
            buttons=data.get("buttons"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    def preview(self, max_len: int = 50) -> str:
        """返回消息文本预览（截断）"""
        if self.text:
            return self.text[:max_len] + ("..." if len(self.text) > max_len else "")
        return "（无文本）"
