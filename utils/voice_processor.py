"""AI 语音生成模块 - 使用 Edge TTS（免费）"""

import asyncio
import logging
import os
import random
import tempfile
from typing import List, Optional

import edge_tts
from telegram import Bot

logger = logging.getLogger(__name__)

# 10 种不同的中文音色（男女声混合，风格多样）
CHINESE_VOICES = [
    "zh-CN-XiaoxiaoNeural",  # 女声-晓晓（温柔）
    "zh-CN-XiaoyiNeural",    # 女声-晓伊（亲切）
    "zh-CN-YunjianNeural",   # 男声-云健（活力）
    "zh-CN-YunxiNeural",     # 男声-云希（稳重）
    "zh-CN-YunyangNeural",   # 男声-云扬（新闻播报）
    "zh-CN-XiaochenNeural",  # 女声-晓辰（客服）
    "zh-CN-XiaohanNeural",   # 女声-晓涵（青春）
    "zh-CN-XiaomengNeural",  # 女声-晓梦（甜美）
    "zh-CN-XiaomoNeural",    # 女声-晓墨（成熟）
    "zh-CN-XiaoqiuNeural",   # 女声-晓秋（温暖）
]


async def generate_voice(text: str, output_path: str, voice: str = None) -> bool:
    """
    生成单条语音

    Args:
        text: 要转换的文字
        output_path: 输出文件路径
        voice: 音色名称（不指定则随机）

    Returns:
        bool: 是否成功
    """
    try:
        if not voice:
            voice = random.choice(CHINESE_VOICES)

        logger.info("🎤 生成语音: %s... (音色: %s)", text[:30], voice)

        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info("✅ 语音生成成功: %s", output_path)
            return True
        else:
            logger.error("❌ 语音文件无效: %s", output_path)
            return False

    except Exception as e:
        logger.error("❌ 语音生成失败: %s", e)
        return False


async def generate_voice_variants(
    text_variants: List[str],
    temp_dir: str = None,
) -> List[str]:
    """
    为多条文案生成语音变体

    Args:
        text_variants: 文案变体列表
        temp_dir: 临时文件目录（默认使用系统临时目录）

    Returns:
        List[str]: 生成的语音文件路径列表
    """
    if temp_dir is None:
        temp_dir = tempfile.mkdtemp(prefix="voices_")
    else:
        os.makedirs(temp_dir, exist_ok=True)

    voice_files = []

    for i, text in enumerate(text_variants):
        output_path = os.path.join(
            temp_dir, f"voice_{i}_{random.randint(1000, 9999)}.mp3"
        )
        voice = CHINESE_VOICES[i % len(CHINESE_VOICES)]

        success = await generate_voice(text, output_path, voice)
        if success:
            voice_files.append(output_path)
        else:
            logger.warning("⚠️ 语音 %d 生成失败，跳过", i)

    logger.info("✅ 共生成 %d/%d 条语音", len(voice_files), len(text_variants))
    return voice_files


async def upload_voice_to_telegram(
    bot: Bot,
    chat_id: int,
    voice_path: str,
    caption: str = None,
) -> Optional[dict]:
    """
    上传语音到 Telegram 并获取 file_id

    Args:
        bot: Telegram Bot 实例
        chat_id: 聊天 ID
        voice_path: 语音文件路径
        caption: 语音描述

    Returns:
        dict: {"file_id": ..., "duration": ...}，失败返回 None
    """
    try:
        with open(voice_path, "rb") as voice_file:
            message = await bot.send_voice(
                chat_id=chat_id,
                voice=voice_file,
                caption=caption or "（临时消息，即将删除）",
            )

        file_id = message.voice.file_id
        duration = message.voice.duration

        await message.delete()

        logger.info("✅ 语音已上传，file_id: %s..., 时长: %d秒", file_id[:20], duration)
        return {"file_id": file_id, "duration": duration}

    except Exception as e:
        logger.error("❌ 语音上传失败: %s", e)
        return None


async def generate_and_upload_voices(
    bot: Bot,
    chat_id: int,
    text_variants: List[str],
    progress_callback=None,
) -> List[dict]:
    """
    生成语音变体并上传到 Telegram

    Args:
        bot: Telegram Bot 实例
        chat_id: 用户 ID
        text_variants: 文案变体列表
        progress_callback: 进度回调函数 async (current, total)

    Returns:
        List[dict]: 语音信息列表 [{"file_id": "xxx", "duration": 10, "index": 0}, ...]
    """
    logger.info("🎤 开始生成 %d 条语音变体...", len(text_variants))

    temp_dir = tempfile.mkdtemp(prefix=f"voices_{chat_id}_")
    voice_files = await generate_voice_variants(text_variants, temp_dir)

    if not voice_files:
        logger.error("❌ 所有语音生成失败")
        return []

    voice_infos = []

    for i, voice_path in enumerate(voice_files):
        if progress_callback:
            await progress_callback(i + 1, len(voice_files))

        voice_info = await upload_voice_to_telegram(
            bot,
            chat_id,
            voice_path,
            caption=f"语音变体 {i + 1}/{len(voice_files)}",
        )

        if voice_info:
            voice_infos.append(
                {
                    "file_id": voice_info["file_id"],
                    "duration": voice_info["duration"],
                    "index": i,
                }
            )

        try:
            os.remove(voice_path)
        except OSError:
            pass

    try:
        os.rmdir(temp_dir)
    except OSError:
        pass

    logger.info("✅ 完成！成功上传 %d 条语音", len(voice_infos))
    return voice_infos
