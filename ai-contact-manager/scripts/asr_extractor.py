"""
ASR 语音转文字模块 — 基于 OpenAI Whisper

支持从录音、语音消息中转录中文文字，
转录结果自动送入本地规则引擎进行联系人信息解析。

依赖安装：
  pip install openai-whisper
  （首次运行会自动下载模型，tiny ~150MB, base ~300MB, small ~1GB）

模型选择建议：
  - tiny:  速度最快，适合快速测试，准确率一般
  - base:  平衡选择，适合日常使用（推荐）
  - small: 准确率更高，速度稍慢
  - medium: 最高准确率，需要更多显存/内存
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# 支持的音频格式
SUPPORTED_AUDIO_FORMATS = (
    ".mp3", ".wav", ".m4a", ".flac", ".ogg",
    ".opus", ".aac", ".wma", ".amr", ".silk",
    ".mp4", ".mov", ".avi",  # 视频文件也尝试提取音频
)


class ASRExtractor:
    """基于 OpenAI Whisper 的语音转文字提取器。"""

    def __init__(
        self,
        model_size: str = "base",
        language: str = "zh",
        use_gpu: bool = False,
    ):
        """
        初始化 ASR 提取器。

        Args:
            model_size: Whisper 模型大小 (tiny/base/small/medium/large)
            language: 目标语言，'zh' = 中文
            use_gpu: 是否使用 GPU 加速
        """
        self.model_size = model_size
        self.language = language
        self.use_gpu = use_gpu
        self._model = None  # 延迟加载

    def _ensure_loaded(self):
        """延迟加载 Whisper 模型。"""
        if self._model is not None:
            return

        try:
            import whisper
            device = "cuda" if self.use_gpu else "cpu"
            self._model = whisper.load_model(self.model_size, device=device)
            logger.info(f"Whisper 模型 ({self.model_size}) 加载完成，设备: {device}")
        except ImportError:
            raise ImportError(
                "openai-whisper 未安装。请运行：\n"
                "  pip install openai-whisper"
            )

    def extract(self, audio_path: str) -> str:
        """
        从音频文件中转写文字。

        Args:
            audio_path: 音频/视频文件路径

        Returns:
            转写后的文字
        """
        self._ensure_loaded()

        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        logger.info(f"正在进行语音转写: {audio_path}")

        try:
            result = self._model.transcribe(
                audio_path,
                language=self.language,
                verbose=False,
            )
        except Exception as e:
            logger.error(f"语音转写失败: {e}")
            raise

        text = result.get("text", "").strip()
        segments = result.get("segments", [])

        logger.info(
            f"ASR 完成，共 {len(segments)} 个语音片段，"
            f"转写 {len(text)} 字符"
        )

        return text

    def extract_with_timestamps(self, audio_path: str) -> dict:
        """
        转写文字并返回带时间戳的结构化结果。

        Returns:
            {
                "full_text": str,        # 完整转写文字
                "segments": [            # 分段列表
                    {
                        "start": float,  # 开始时间（秒）
                        "end": float,    # 结束时间（秒）
                        "text": str,     # 该段文字
                    }
                ],
                "language": str,         # 检测到的语言
                "duration": float,       # 音频总时长（秒）
                "source": "asr",
            }
        """
        self._ensure_loaded()

        result = self._model.transcribe(
            audio_path,
            language=self.language,
            verbose=False,
        )

        segments = []
        for seg in result.get("segments", []):
            segments.append({
                "start": round(seg["start"], 2),
                "end": round(seg["end"], 2),
                "text": seg["text"].strip(),
            })

        return {
            "full_text": result.get("text", "").strip(),
            "segments": segments,
            "language": result.get("language", self.language),
            "duration": round(result.get("segments", [{}])[-1].get("end", 0), 2) if result.get("segments") else 0,
            "source": "asr",
        }


def transcribe_audio(audio_path: str, model_size: str = "base") -> str:
    """便捷函数：从音频文件中转写文字。"""
    extractor = ASRExtractor(model_size=model_size)
    return extractor.extract(audio_path)


def is_audio_file(filepath: str) -> bool:
    """判断文件是否为支持的音频/视频格式。"""
    ext = os.path.splitext(filepath)[1].lower()
    return ext in SUPPORTED_AUDIO_FORMATS


def is_image_file(filepath: str) -> bool:
    """判断文件是否为支持的图片格式。"""
    ext = os.path.splitext(filepath)[1].lower()
    return ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp", ".gif")
