# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
AI人脉关系管家 — 主入口脚本

支持三种输入格式：
  - 文本：直接读取 .txt 文件或 --text 参数
  - 图片：OCR 识别后提取文字（截图、名片、照片）
  - 音频：语音转文字后提取信息（录音、语音消息）

用法：
  python extract_contacts.py --input sample.txt --mode local
  python extract_contacts.py --input screenshot.png --input-type image --mode local
  python extract_contacts.py --input recording.mp3 --input-type audio --mode local
  python extract_contacts.py --input file.mp3 --mode local     # 自动检测为音频
"""

import argparse
import json
import logging
import os
import sys

# 将 scripts 目录加入 path，支持模块导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from local_extractor import LocalExtractor
from llm_extractor import LLMExtractor
from generate_reminders import generate_all
from asr_extractor import is_audio_file, is_image_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ========== 文件类型检测 ==========

TEXT_EXTENSIONS = (".txt", ".md", ".csv", ".log", "")


def _detect_input_type(filepath: str) -> str:
    """根据文件后缀名自动检测输入类型。"""
    ext = os.path.splitext(filepath)[1].lower()
    if is_image_file(filepath):
        return "image"
    if is_audio_file(filepath):
        return "audio"
    if ext in TEXT_EXTENSIONS:
        return "text"
    # 无后缀或未知后缀，默认按文本尝试
    return "text"


# ========== 文本读取（从不同来源） ==========

def _read_text_input(filename: str) -> str:
    """直接读取文本文件。"""
    with open(filename, "r", encoding="utf-8") as f:
        return f.read()


def _read_image_input(filename: str, ocr_config: dict) -> str:
    """通过 OCR 从图片中提取文字。"""
    try:
        from ocr_extractor import OCRExtractor
    except ImportError:
        raise ImportError("OCR 模块未找到，请确认 ocr_extractor.py 在 scripts/ 目录下")

    extractor = OCRExtractor(
        use_gpu=ocr_config.get("use_gpu", False),
        lang=ocr_config.get("lang", "ch"),
    )
    text = extractor.extract(filename)
    if not text.strip():
        logger.warning("OCR 未识别到任何文字，可能是空白图片或清晰度不足")
    return text


def _read_audio_input(filename: str, asr_config: dict) -> str:
    """通过 ASR 从音频中转录文字。"""
    try:
        from asr_extractor import ASRExtractor
    except ImportError:
        raise ImportError("ASR 模块未找到，请确认 asr_extractor.py 在 scripts/ 目录下")

    extractor = ASRExtractor(
        model_size=asr_config.get("model_size", "base"),
        language=asr_config.get("language", "zh"),
        use_gpu=asr_config.get("use_gpu", False),
    )
    text = extractor.extract(filename)
    if not text.strip():
        logger.warning("ASR 未识别到任何语音内容")
    return text


# ========== 主入口 ==========

def main():
    parser = argparse.ArgumentParser(
        description="AI人脉关系管家 — 多格式输入、智能提取与联系提醒",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
输入类型与示例:
  # 文本输入（默认）
  %(prog)s -i data/sample_notes.txt -m local

  # 图片输入（聊天截图/名片/照片）
  %(prog)s -i screenshot.png -m local
  %(prog)s -i business_card.jpg --input-type image -m local

  # 音频输入（录音/语音消息）
  %(prog)s -i recording.mp3 -m local
  %(prog)s -i voice.m4a --input-type audio --asr-model-size tiny

  # 混合模式（本地 + LLM 增强）
  %(prog)s -i screenshot.png -m hybrid --llm-api-key sk-xxx
        """,
    )

    # ==== 输入参数 ====
    parser.add_argument("--input", "-i", required=True,
                        help="输入文件路径（文本/图片/音频）")
    parser.add_argument("--text", "-t",
                        help="直接输入文本（与 --input 二选一）")
    parser.add_argument(
        "--input-type",
        choices=["text", "image", "audio", "auto"],
        default="auto",
        help="输入类型。auto = 根据文件后缀自动检测（默认）",
    )

    # ==== 模式参数 ====
    parser.add_argument(
        "--mode", "-m",
        choices=["local", "llm", "hybrid"],
        default="local",
        help="提取模式（默认: local）",
    )

    # ==== LLM 参数 ====
    parser.add_argument("--llm-provider", default="deepseek",
                        choices=["openai", "deepseek", "custom"])
    parser.add_argument("--llm-api-key", help="LLM API 密钥")
    parser.add_argument("--llm-model", help="模型名称")
    parser.add_argument("--llm-base-url", help="自定义 API 端点")

    # ==== OCR 参数 ====
    parser.add_argument("--ocr-gpu", action="store_true",
                        help="OCR 使用 GPU 加速")
    parser.add_argument("--ocr-lang", default="ch",
                        help="OCR 语言（ch=中英混合，en=英文）")

    # ==== ASR 参数 ====
    parser.add_argument("--asr-model-size", default="base",
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper 模型大小（默认 base）")
    parser.add_argument("--asr-gpu", action="store_true",
                        help="ASR 使用 GPU 加速")
    parser.add_argument("--asr-language", default="zh",
                        help="ASR 语言（zh=中文，en=英文）")

    # ==== 输出参数 ====
    parser.add_argument("--output-dir", "-o", default="outputs",
                        help="输出目录（默认: outputs）")
    parser.add_argument("--max-reminders", type=int, default=10,
                        help="最大提醒条数")
    parser.add_argument("--rules", help="自定义规则文件路径")

    # ==== 隐私参数 ====
    parser.add_argument("--encrypt", action="store_true",
                        help="加密输出的 contacts.json（需要 --password）")
    parser.add_argument("--password", help="加密/解密密码")
    parser.add_argument("--no-review-queue", action="store_true",
                        help="跳过生成关系确认队列")

    # ==== 其他 ====
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="详细日志输出")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # ========== Step 1: 读取输入（多格式分流） ==========
    if args.text:
        text = args.text
        input_source = "text_cli"
    else:
        if not os.path.exists(args.input):
            logger.error(f"输入文件不存在: {args.input}")
            sys.exit(1)

        # 自动检测或使用手动指定的类型
        input_type = args.input_type
        if input_type == "auto":
            input_type = _detect_input_type(args.input)

        logger.info(f"输入文件: {args.input}")
        logger.info(f"输入类型: {input_type}")

        if input_type == "text":
            text = _read_text_input(args.input)
            input_source = "text_file"

        elif input_type == "image":
            ocr_config = {
                "use_gpu": args.ocr_gpu,
                "lang": args.ocr_lang,
            }
            text = _read_image_input(args.input, ocr_config)
            input_source = f"ocr_{ocr_config['lang']}"
            logger.info(f"OCR 提取文字: {len(text)} 字符")

        elif input_type == "audio":
            asr_config = {
                "model_size": args.asr_model_size,
                "language": args.asr_language,
                "use_gpu": args.asr_gpu,
            }
            text = _read_audio_input(args.input, asr_config)
            input_source = f"asr_whisper_{asr_config['model_size']}"
            logger.info(f"ASR 转写文字: {len(text)} 字符")

        else:
            logger.error(f"未知的输入类型: {input_type}")
            sys.exit(1)

    if not text.strip():
        logger.error("输入文本为空（OCR/ASR 可能未识别到内容）。")
        sys.exit(1)

    logger.info(f"最终文本长度: {len(text)} 字符")

    # ========== Step 2: 提取 ==========
    logger.info(f"提取模式: {args.mode}")

    if args.mode == "local":
        extractor = LocalExtractor(rules_path=args.rules)
        result = extractor.extract(text)

    elif args.mode == "llm":
        if not args.llm_api_key:
            logger.error("LLM 模式需要提供 --llm-api-key。")
            sys.exit(1)
        extractor = LLMExtractor(
            provider=args.llm_provider,
            api_key=args.llm_api_key,
            model=args.llm_model,
            base_url=args.llm_base_url,
        )
        result = extractor.extract(text)

    elif args.mode == "hybrid":
        local_extractor = LocalExtractor(rules_path=args.rules)
        local_result = local_extractor.extract(text)

        high_conf = []
        low_conf = []
        for contact in local_result.get("contacts", []):
            if contact.get("confidence", 0) >= 0.6:
                high_conf.append(contact)
            else:
                low_conf.append(contact)

        logger.info(
            f"本地引擎: {len(high_conf)} 条高置信度, {len(low_conf)} 条低置信度"
        )

        if low_conf and args.llm_api_key:
            logger.info("启动 LLM 增强处理低置信度条目...")
            llm_extractor = LLMExtractor(
                provider=args.llm_provider,
                api_key=args.llm_api_key,
                model=args.llm_model,
                base_url=args.llm_base_url,
            )
            llm_result = llm_extractor.extract(text, low_confidence_items=low_conf)
            merged_contacts = high_conf + llm_result.get("contacts", [])
            result = {
                "contacts": merged_contacts,
                "extraction_method": "hybrid",
                "local_high_confidence": len(high_conf),
                "llm_enhanced": len(llm_result.get("contacts", [])),
                "total_contacts": len(merged_contacts),
            }
        else:
            result = local_result
            if low_conf and not args.llm_api_key:
                logger.warning(
                    f"有 {len(low_conf)} 条低置信度结果，"
                    "配置 --llm-api-key 可启用 LLM 增强。"
                )

    # 标注数据来源
    result["input_source"] = input_source
    result.setdefault("extraction_method", "local")

    logger.info(
        f"提取完成，共 {result.get('total_contacts', len(result.get('contacts', [])))} 个联系人"
    )

    # ========== Step 3: 输出 ==========
    os.makedirs(args.output_dir, exist_ok=True)

    contacts_path = os.path.join(args.output_dir, "contacts.json")
    with open(contacts_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"联系人数据 → {contacts_path}")

    log_path = os.path.join(args.output_dir, "extraction_log.json")
    log_data = {
        "input_file": args.input if not args.text else "(cli text)",
        "input_type": input_source,
        "input_length": len(text),
        "mode": args.mode,
        "extraction_method": result.get("extraction_method", "local"),
        "total_contacts": result.get("total_contacts", len(result.get("contacts", []))),
        "per_contact_confidence": [
            {"name": c.get("name"), "confidence": c.get("confidence"), "source": c.get("source")}
            for c in result.get("contacts", [])
        ],
    }
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

    try:
        reminder_outputs = generate_all(
            contacts_data=result,
            output_dir=args.output_dir,
            max_reminders=args.max_reminders,
        )
        logger.info(f"提醒数据 → {reminder_outputs['reminders_json']}")
        logger.info(f"提醒报告 → {reminder_outputs['reminders_md']}")
    except Exception as e:
        logger.error(f"提醒生成失败: {e}")

    # ========== Step 4: 关系确认队列 ==========
    review_path = None
    if not args.no_review_queue:
        try:
            from review_queue import ReviewQueue
            import json as _json_mod
            # 读取刚生成的 reminders.json 获取关系分析结果
            reminders_json_path = os.path.join(args.output_dir, "reminders.json")
            relationship_analysis = None
            if os.path.exists(reminders_json_path):
                with open(reminders_json_path, "r", encoding="utf-8") as f:
                    reminders_data = _json_mod.load(f)
                    relationship_analysis = reminders_data.get("relationship_analysis")

            rq = ReviewQueue()
            rq.scan(result.get("contacts", []), relationship_analysis)
            review_path = os.path.join(args.output_dir, "REVIEW_QUEUE.md")
            rq.generate_markdown(review_path)
            logger.info(f"关系确认队列 → {review_path} ({len(rq.queue)} 项)")
        except Exception as e:
            logger.warning(f"关系确认队列生成失败: {e}")

    # ========== Step 5: 隐私加密（可选） ==========
    if args.encrypt:
        if not args.password:
            logger.error("加密需要提供 --password。")
            sys.exit(1)

        # 检查密码强度
        try:
            from privacy_manager import PrivacyManager
            pm = PrivacyManager(args.output_dir)
            strength = pm.check_password_strength(args.password)
            if strength["level"] == "弱":
                logger.warning(f"密码强度: {strength['level']}。建议: {', '.join(strength['suggestions'])}")
            pm.encrypt_file(contacts_path, args.password)
            logger.info(f"contacts.json 已加密")
        except ImportError:
            logger.error("加密功能需要 pycryptodome。安装: pip install pycryptodome")
        except Exception as e:
            logger.error(f"加密失败: {e}")

    # ========== 完成 ==========
    print(f"\n✅ 处理完成！（输入来源: {input_source}）")
    print(f"   📊 联系人数据: {contacts_path}{' 🔒 已加密' if args.encrypt else ''}")
    print(f"   📝 提取日志:   {log_path}")
    print(f"   🔔 提醒报告:   {os.path.join(args.output_dir, 'reminders.md')}")
    print(f"   📋 提醒数据:   {os.path.join(args.output_dir, 'reminders.json')}")
    if review_path:
        print(f"   📋 确认队列:   {review_path}")
    print(f"\n   👥 共提取 {result.get('total_contacts', len(result.get('contacts', [])))} 个联系人")


if __name__ == "__main__":
    main()
