"""AI 语音生成模块 - 使用 OpenAI TTS（语音消息格式）"""

from openai import OpenAI
import logging
import os
import random
from typing import List, Optional
from telegram import Bot
from pydub import AudioSegment

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]


def generate_voice(text: str, output_path: str, voice: str = None) -> bool:
    """生成单条语音（使用 OpenAI TTS）"""
    try:
        if not OPENAI_API_KEY:
            logger.error("❌ 未配置 OPENAI_API_KEY")
            return False
        
        if not voice:
            voice = random.choice(VOICES)
        
        logger.info(f"🎤 生成语音: {text[:30]}... (音色: {voice})")
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
            speed=1.0,
            response_format="mp3"  # 确保是 mp3 格式
        )
        
        response.stream_to_file(output_path)
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"✅ 语音生成成功: {os.path.getsize(output_path)} bytes")
            return True
        return False
            
    except Exception as e:
        logger.error(f"❌ 语音生成失败: {e}")
        return False


def generate_voice_variants(text_variants: List[str], temp_dir: str = "/tmp/voices") -> List[str]:
    """为多条文案生成语音变体"""
    os.makedirs(temp_dir, exist_ok=True)
    voice_files = []
    
    total_chars = sum(len(text) for text in text_variants)
    estimated_cost = (total_chars / 1_000_000) * 15
    logger.info(f"💰 预计消费: ${estimated_cost:.4f} (约 ¥{estimated_cost * 7.2:.2f})")
    
    for i, text in enumerate(text_variants):
        output_path = os.path.join(temp_dir, f"voice_{i}_{random.randint(1000, 9999)}.mp3")
        voice = VOICES[i % len(VOICES)]
        
        if generate_voice(text, output_path, voice):
            voice_files.append(output_path)
        else:
            logger.warning(f"⚠️ 语音 {i} 生成失败，跳过")
    
    logger.info(f"✅ 共生成 {len(voice_files)}/{len(text_variants)} 条语音")
    return voice_files


async def upload_voice_to_telegram(bot: Bot, chat_id: int, voice_path: str, caption: str = None) -> Optional[dict]:
    """上传语音到 Telegram（尝试语音消息格式）"""
    try:
        # 先尝试 send_voice（语音消息格式）
        try:
            with open(voice_path, 'rb') as voice_file:
                message = await bot.send_voice(
                    chat_id=chat_id,
                    voice=voice_file,
                    caption=None  # 不显示标题
                )
                
                file_id = message.voice.file_id
                duration = message.voice.duration
                await message.delete()
                
                logger.info(f"✅ 语音消息已上传（voice 格式），时长: {duration}秒")
                return {"file_id": file_id, "duration": duration}
        
        except Exception as voice_error:
            # 如果 send_voice 失败，尝试 send_audio
            logger.warning(f"⚠️ send_voice 失败: {voice_error}，尝试 send_audio...")
            
            with open(voice_path, 'rb') as audio_file:
                message = await bot.send_audio(
                    chat_id=chat_id,
                    audio=audio_file,
                    title="",  # 空标题
                    performer="",  # 空演唱者
                    caption=None
                )
                
                file_id = message.audio.file_id
                duration = message.audio.duration
                await message.delete()
                
                logger.info(f"✅ 音频已上传（audio 格式），时长: {duration}秒")
                return {"file_id": file_id, "duration": duration}
                
    except Exception as e:
        logger.error(f"❌ 语音上传失败: {e}")
        return None


async def generate_and_upload_voices(bot: Bot, chat_id: int, text_variants: List[str], progress_callback=None) -> List[dict]:
    """生成语音变体并上传到 Telegram"""
    logger.info(f"🎤 开始生成 {len(text_variants)} 条语音变体（OpenAI TTS）...")
    
    temp_dir = f"/tmp/voices_{chat_id}_{random.randint(1000, 9999)}"
    voice_files = generate_voice_variants(text_variants, temp_dir)
    
    if not voice_files:
        logger.error("❌ 所有语音生成失败")
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
        
        try:
            os.remove(voice_path)
        except:
            pass
    
    try:
        os.rmdir(temp_dir)
    except:
        pass
    
    logger.info(f"✅ 完成！成功上传 {len(voice_infos)} 条语音")
    return voice_infos
