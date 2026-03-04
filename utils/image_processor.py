"""图片变体生成模块"""

import io
import logging
import random
from typing import List

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance

logger = logging.getLogger(__name__)


def generate_image_variants(image_bytes: bytes, count: int = 10) -> List[bytes]:
    """
    从原图生成多个防检测变体。

    Args:
        image_bytes: 原始图片字节流
        count: 生成数量（默认10）

    Returns:
        List[bytes]: 变体图片字节流列表
    """
    try:
        variants = []
        original = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        for i in range(count):
            img = original.copy()

            # 1. 添加随机像素噪点
            img = _add_noise(img, intensity=random.randint(2, 5))

            # 2. 调整亮度和对比度
            img = _adjust_brightness_contrast(img)

            # 3. 添加不可见水印
            img = _add_invisible_watermark(img, seed=i)

            # 4. 轻微裁剪和缩放
            img = _random_crop_scale(img)

            # 5. 转换为字节流
            output = io.BytesIO()
            quality = random.randint(92, 98)
            img.save(output, format="JPEG", quality=quality, optimize=True)
            variants.append(output.getvalue())

            logger.info("生成图片变体 %d/%d", i + 1, count)

        return variants

    except Exception as e:
        logger.error("生成图片变体失败: %s", e)
        return []


def _add_noise(img: Image.Image, intensity: int = 3) -> Image.Image:
    """添加随机像素噪点"""
    img_array = np.array(img)
    noise = np.random.randint(-intensity, intensity + 1, img_array.shape, dtype=np.int16)
    noisy = np.clip(img_array.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(noisy)


def _adjust_brightness_contrast(img: Image.Image) -> Image.Image:
    """轻微调整亮度和对比度"""
    brightness = ImageEnhance.Brightness(img)
    img = brightness.enhance(random.uniform(0.97, 1.03))

    contrast = ImageEnhance.Contrast(img)
    img = contrast.enhance(random.uniform(0.98, 1.02))

    return img


def _add_invisible_watermark(img: Image.Image, seed: int) -> Image.Image:
    """添加随机位置的不可见水印"""
    width, height = img.size
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    rng = random.Random(seed)
    x = rng.randint(10, max(10, min(width - 10, width - 50)))
    y = rng.randint(10, max(10, min(height - 10, height - 30)))

    draw.text((x, y), f"v{seed}", fill=(255, 255, 255, 2))

    img_rgba = img.convert("RGBA")
    result = Image.alpha_composite(img_rgba, overlay)
    return result.convert("RGB")


def _random_crop_scale(img: Image.Image) -> Image.Image:
    """轻微随机裁剪和缩放"""
    width, height = img.size

    crop_percent = random.uniform(0.005, 0.02)
    left = int(width * crop_percent * random.random())
    top = int(height * crop_percent * random.random())
    right = width - int(width * crop_percent * random.random())
    bottom = height - int(height * crop_percent * random.random())

    right = max(right, left + 1)
    bottom = max(bottom, top + 1)

    img = img.crop((left, top, right, bottom))
    img = img.resize((width, height), Image.Resampling.LANCZOS)

    return img
