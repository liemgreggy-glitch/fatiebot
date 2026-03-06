"""AI 语音生成模块 - Fish Audio TTS（3个中文甜美女声随机切换）"""

import requests
import logging
import os
import random
import time
from typing import List, Optional
from telegram import Bot

logger = logging.getLogger(__name__)

# Fish Audio 配置
FISH_API_KEY = os.getenv("FISH_API_KEY")
FISH_API_URL = "https://api.fish.audio/v1/tts"

# 🎀 Fish Audio 中文甜美女声（3个随机切换）
FISH_VOICES = [
    {
        "reference_id": "fbe02f8306fc4d3d915e9871722a39d5",
        "name": "甜美女声1",
        "desc": "年轻活泼"
    },
    {
        "reference_id": "f82e3885ac22468eb6c773b96f2c5752",
        "name": "甜美女声2",
        "desc": "温柔可爱"
    },
    {
        "reference_id": "5c353fdb312f4888836a9a5680099ef0",
        "name": "甜美女声3",
        "desc": "甜美萝莉"
    },
]


def generate_voice(text: str, output_path: str, voice_config: dict = None) -> bool:
    """生成单条语音（Fish Audio）"""
    try:
        if not FISH_API_KEY:
            logger.error("❌ 未配置 FISH_API_KEY")
            return False
        
        if not voice_config:
            voice_config = random.choice(FISH_VOICES)
        
        logger.info(f"🎤 生成语音: {text[:30]}... ({voice_config['name']} - {voice_config['desc']})")
        
        # 构建请求
        headers = {
            "Authorization": f"Bearer {FISH_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "text": text,
            "reference_id": voice_config["reference_id"],
            "format": "mp3",
            "mp3_bitrate": 128,
            "normalize": True,
            "latency": "normal"
        }
        
        # 发送请求
        response = requests.post(
            FISH_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            # 保存音频
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            file_size = os.path.getsize(output_path)
            logger.info(f"✅ Fish Audio 语音生成成功 ({file_size} 字节)")
            return True
        else:
            logger.error(f"❌ Fish Audio API 错误: {response.status_code}")
            logger.error(f"   响应: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ 语音生成失败: {e}")
        return False


def generate_voice_variants(text_variants: List[str], temp_dir: str = "/tmp/voices") -> List[str]:
    """为多条文案生成语音变体"""
    os.makedirs(temp_dir, exist_ok=True)
    voice_files = []
    
    logger.info(f"🎀 使用 Fish Audio 中文甜美女声: {len(FISH_VOICES)} 种（随机切换）")
    
    for i, text in enumerate(text_variants):
        output_path = os.path.join(temp_dir, f"voice_{i}_{random.randint(1000, 9999)}.mp3")
        voice_config = FISH_VOICES[i % len(FISH_VOICES)]
        
        logger.info(f"📝 第 {i+1} 条使用: {voice_config['name']} ({voice_config['desc']})")
        
        if generate_voice(text, output_path, voice_config):
            voice_files.append(output_path)
            time.sleep(0.5)  # 避免请求过快
        else:
            logger.warning(f"⚠️  第 {i+1} 条生成失败，跳过")
    
    logger.info(f"✅ 共生成 {len(voice_files)}/{len(text_variants)} 条语音")
    return voice_files


async def upload_voice_to_telegram(bot: Bot, chat_id: int, voice_path: str, caption: str = None) -> Optional[dict]:
    """上传语音到 Telegram"""
    try:
        try:
            with open(voice_path, 'rb') as voice_file:
                message = await bot.send_voice(chat_id=chat_id, voice=voice_file)
                file_id = message.voice.file_id
                duration = message.voice.duration
                await message.delete()
                logger.info(f"✅ 语音已上传到 Telegram (file_id: {file_id[:20]}..., {duration}秒)")
                return {"file_id": file_id, "duration": duration}
        except Exception as voice_error:
            logger.warning(f"⚠️  语音格式上传失败，尝试音频格式: {voice_error}")
            with open(voice_path, 'rb') as audio_file:
                message = await bot.send_audio(chat_id=chat_id, audio=audio_file)
                file_id = message.audio.file_id
                duration = message.audio.duration
                await message.delete()
                logger.info(f"✅ 音频已上传到 Telegram (file_id: {file_id[:20]}..., {duration}秒)")
                return {"file_id": file_id, "duration": duration}
    except Exception as e:
        logger.error(f"❌ 上传到 Telegram 失败: {e}")
        return None


async def generate_and_upload_voices(bot: Bot, chat_id: int, text_variants: List[str], progress_callback=None) -> List[dict]:
    """生成语音变体并上传到 Telegram"""
    logger.info(f"🎤 开始生成 {len(text_variants)} 条语音（Fish Audio 中文甜美女声，3种随机切换）...")
    
    temp_dir = f"/tmp/voices_{chat_id}_{random.randint(1000, 9999)}"
    voice_files = generate_voice_variants(text_variants, temp_dir)
    
    if not voice_files:
        logger.error("❌ 没有生成任何语音文件")
        return []
    
    voice_infos = []
    for i, voice_path in enumerate(voice_files):
        if progress_callback:
            await progress_callback(i + 1, len(voice_files))
        
        voice_info = await upload_voice_to_telegram(bot, chat_id, voice_path)
        if voice_info:
            voice_infos.append({
                "file_id": voice_info['file_id'],
                "duration": voice_info['duration'],
                "index": i
            })
        
        # 删除临时文件
        try:
            os.remove(voice_path)
        except Exception as e:
            logger.warning(f"⚠️  删除临时文件失败: {e}")
    
    # 删除临时目录
    try:
        os.rmdir(temp_dir)
    except Exception as e:
        logger.warning(f"⚠️  删除临时目录失败: {e}")
    
    logger.info(f"✅ 完成！成功上传 {len(voice_infos)}/{len(text_variants)} 条语音到 Telegram")
    return voice_infos
