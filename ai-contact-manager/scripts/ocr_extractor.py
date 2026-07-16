"""
OCR 图片文字提取模块 — 基于 PaddleOCR

支持从聊天截图、名片、照片等图片中提取中文文字，
提取结果自动送入本地规则引擎进行联系人信息解析。

依赖安装：
  pip install paddlepaddle paddleocr
  （首次运行会自动下载模型，约 200MB）
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class OCRExtractor:
    """基于 PaddleOCR 的图片文字提取器。"""

    def __init__(self, use_gpu: bool = False, lang: str = "ch"):
        """
        初始化 OCR 提取器。

        Args:
            use_gpu: 是否使用 GPU 加速（需要 CUDA）
            lang: 识别语言，'ch' = 中英混合
        """
        self.use_gpu = use_gpu
        self.lang = lang
        self._ocr = None  # 延迟加载

    def _ensure_loaded(self):
        """延迟加载 PaddleOCR 模型（首次调用时才加载，节省启动时间）。"""
        if self._ocr is not None:
            return

        try:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(
                use_angle_cls=True,  # 文本方向分类（处理竖排文字）
                lang=self.lang,
                use_gpu=self.use_gpu,
            )
            logger.info("PaddleOCR 模型加载完成")
        except ImportError:
            raise ImportError(
                "PaddleOCR 未安装。请运行：\n"
                "  pip install paddlepaddle paddleocr\n"
                "  注意：paddlepaddle 需选择正确的版本（CPU/GPU），参考官方文档。"
            )

    def extract(self, image_path: str) -> str:
        """
        从图片中提取文字。

        Args:
            image_path: 图片文件路径（支持 jpg/png/bmp/tiff 等常见格式）

        Returns:
            提取到的全部文字，按行拼接为字符串
        """
        self._ensure_loaded()

        logger.info(f"正在进行 OCR 识别: {image_path}")

        try:
            result = self._ocr.ocr(image_path, cls=True)
        except Exception as e:
            logger.error(f"OCR 识别失败: {e}")
            raise

        if not result or not result[0]:
            logger.warning("未从图片中识别到任何文字")
            return ""

        # 提取所有检测框中的文字，按阅读顺序拼接
        lines = []
        for line_group in result:
            for line_info in line_group:
                text = line_info[1][0]  # (bbox, (text, confidence))
                confidence = line_info[1][1]
                if confidence > 0.5:  # 过滤低置信度文字
                    lines.append(text)
                else:
                    logger.debug(f"丢弃低置信度文字 ({confidence:.2f}): {text}")

        full_text = "\n".join(lines)
        logger.info(f"OCR 完成，识别到 {len(lines)} 行文字，共 {len(full_text)} 字符")
        return full_text

    def extract_and_format(self, image_path: str) -> dict:
        """
        提取文字并返回结构化结果。

        Returns:
            {
                "raw_text": str,           # 完整文字
                "line_count": int,         # 识别行数
                "avg_confidence": float,   # 平均置信度
                "source": "ocr",           # 数据来源
            }
        """
        text = self.extract(image_path)
        return {
            "raw_text": text,
            "line_count": text.count("\n") + 1 if text else 0,
            "avg_confidence": None,  # PaddleOCR 单次调用不便统计均值，可后续增强
            "source": "ocr",
        }


def ocr_image(image_path: str, use_gpu: bool = False) -> str:
    """便捷函数：从图片中提取文字。"""
    extractor = OCRExtractor(use_gpu=use_gpu)
    return extractor.extract(image_path)
