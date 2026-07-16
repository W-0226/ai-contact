# -*- coding: utf-8 -*-
"""
本地规则提取引擎 — 基于正则表达式和关键词词典，
从非结构化聊天备注中提取联系人信息。

不依赖外部 API，所有处理在本地完成。
"""

import re
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class LocalExtractor:
    """本地规则提取器，基于正则 + 关键词匹配。"""

    def __init__(self, rules_path: str = None):
        """
        初始化提取器并加载规则配置。

        Args:
            rules_path: extraction_rules.json 的路径，
                        默认从 references/ 目录加载。
        """
        self.rules = self._load_rules(rules_path)

    def _load_rules(self, rules_path: Optional[str] = None) -> Dict:
        """加载提取规则配置。"""
        if rules_path is None:
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            rules_path = os.path.join(base_dir, "references", "extraction_rules.json")

        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"规则文件未找到: {rules_path}，使用内置默认规则。")
            return self._default_rules()

    def _default_rules(self) -> Dict:
        """内置默认规则，作为配置文件的兜底。"""
        return {
            "birthday_patterns": [
                # 公历：X月X号/日、X-X、X.X
                r"(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*[号日]",
                r"(?P<month>\d{1,2})[\.\-/](?P<day>\d{1,2})",
                # 中文数字月日：三月十五号
                r"(?P<month_cn>[一二三四五六七八九十]{1,2})月(?P<day_cn>[一二三四五六七八九十廿卅]{1,3})[号日]",
                # 农历：腊月初八、正月初一
                r"(腊月|正月|冬月|[一二三四五六七八九十]月)(初[一二三四五六七八九十]|[一二两][一二三四五六七八九十]|三十)",
            ],
            "hobby_keywords": [
                "钓鱼", "打篮球", "打乒乓球", "打羽毛球", "打网球",
                "跑步", "健身", "游泳", "登山", "骑行", "滑雪",
                "看书", "看电影", "看剧", "听音乐", "唱歌",
                "摄影", "画画", "书法", "茶道", "咖啡",
                "打游戏", "编程", "旅游", "做饭", "烘焙",
                "养花", "养宠物", "收藏", "手办", "乐高",
            ],
            "event_keywords": [
                "换工作", "跳槽", "入职", "离职", "升职",
                "结婚", "生孩子", "搬", "买房", "买车",
                "创业", "开公司", "合作", "项目", "融资",
                "出国", "回国", "毕业", "考上", "考过",
            ],
            "tag_keywords": {
                "创业者": ["创业", "开公司", "创始人", "CEO", "老板"],
                "程序员": ["程序员", "开发", "写代码", "前端", "后端"],
                "学生": ["学生", "在读", "大学", "研究生", "博士"],
                "已婚": ["老婆", "老公", "结婚", "妻子", "丈夫"],
                "有孩子": ["孩子", "小孩", "儿子", "女儿", "宝宝"],
                "单身": ["单身", "未婚"],
            },
            "alias_indicators": ["也叫", "小名", "外号", "英文名", "大家都叫"],
        }

    # ========== 公开接口 ==========

    def extract(self, text: str) -> Dict:
        """
        从文本中提取所有联系人的结构化信息。

        Args:
            text: 非结构化聊天备注文本。

        Returns:
            包含 contacts 列表和元信息的字典。
        """
        # Step 1: 按联系人分段
        segments = self._split_by_contact(text)

        contacts = []
        for segment in segments:
            name = segment.get("name", "未知联系人")
            raw_text = segment.get("text", segment.get("raw", ""))

            contact = {
                "name": name,
                "aliases": [],
                "birthday": None,
                "hobbies": [],
                "key_events": [],
                "tags": [],
                "notes": raw_text.strip() if len(raw_text.strip()) < 500 else "",
            }

            # 提取各类信息
            contact["aliases"] = self._extract_aliases(raw_text)
            contact["birthday"] = self._extract_birthday(raw_text)
            contact["hobbies"] = self._extract_hobbies(raw_text)
            contact["key_events"] = self._extract_events(raw_text)
            contact["tags"] = self._extract_tags(raw_text)

            # 计算置信度
            contact["confidence"] = self._calc_confidence(contact)
            contact["source"] = "local"

            contacts.append(contact)

        return {
            "contacts": contacts,
            "extraction_method": "local",
            "generated_at": datetime.now().isoformat(),
            "total_contacts": len(contacts),
        }

    # ========== 分段逻辑 ==========

    def _split_by_contact(self, text: str) -> List[Dict]:
        """
        将文本按联系人分段。

        策略：
        1. 按空行（连续换行）首先分段
        2. 在每段中识别联系人名称
        3. 如果某段无法识别名称，尝试按句号/分号再切
        """
        # 按空行分段
        raw_segments = re.split(r"\n\s*\n", text.strip())

        # 按逗号/分号/句号再次细分长段落
        segments = []
        for seg in raw_segments:
            seg = seg.strip()
            if not seg:
                continue
            # 如果段落太长（>150字符），尝试按句号细分
            if len(seg) > 150:
                sub_segs = re.split(r"[。；;]", seg)
                segments.extend([s.strip() for s in sub_segs if s.strip()])
            else:
                segments.append(seg)

        # 尝试为每段提取联系人名
        result = []
        for seg in segments:
            name = self._extract_contact_name(seg)
            result.append({"name": name, "text": seg})

        return result

    def _extract_contact_name(self, text: str) -> str:
        """
        从段落中提取联系人名称。

        策略：
        - 中文：2-3个汉字开头，且后跟逗号或"是"等的可能是名字
        - 称呼模式：X总、X哥、X姐、老X、小X
        """
        # 称呼模式：张总、老王、小李、X哥
        title_pattern = r"(?:老[A-Za-z\u4e00-\u9fff]|小[A-Za-z\u4e00-\u9fff]|[A-Za-z\u4e00-\u9fff]{1,2}(?:总|哥|姐|老师|同学|经理|教授))"
        match = re.search(title_pattern, text)
        if match:
            return match.group()

        # 中文姓名模式（2-3个汉字）
        name_pattern = r"^([\u4e00-\u9fff]{2,3})[，,]"
        match = re.search(name_pattern, text)
        if match:
            return match.group(1)

        # 英文名
        eng_pattern = r"\b([A-Z][a-z]+)\b"
        matches = re.findall(eng_pattern, text)
        if matches:
            return matches[0]

        return "未知联系人"

    # ========== 各类信息提取 ==========

    def _extract_aliases(self, text: str) -> List[str]:
        """提取别名（绰号、英文名等）。"""
        aliases = []
        for indicator in self.rules.get("alias_indicators", []):
            pattern = rf"{indicator}\s*[：:]*\s*([^\s，。,.]{{1,10}})"
            match = re.search(pattern, text)
            if match:
                aliases.append(match.group(1))
        return aliases

    def _extract_birthday(self, text: str) -> Optional[Dict]:
        """
        提取生日信息。

        Returns:
            {"month": int, "day": int, "type": "solar"|"lunar"|"unknown", "raw": str}
            或 None。
        """
        patterns = self.rules.get("birthday_patterns", [])

        for pattern in patterns:
            match = re.search(pattern, text)
            if not match:
                continue

            # 上下文确认是生日相关
            context_start = max(0, match.start() - 20)
            context_end = min(len(text), match.end() + 10)
            context = text[context_start:context_end]

            if not self._is_birthday_context(context):
                continue

            # 解析数字月日
            if match.groupdict().get("month") and match.groupdict().get("day"):
                return {
                    "month": int(match.group("month")),
                    "day": int(match.group("day")),
                    "type": "solar",
                    "raw": match.group(),
                }

            # 中文数字月日
            if match.groupdict().get("month_cn"):
                month = self._cn_num_to_int(match.group("month_cn"))
                day = self._cn_num_to_int(match.group("day_cn", ""))
                if month and day:
                    return {
                        "month": month,
                        "day": day,
                        "type": "solar",
                        "raw": match.group(),
                    }

            # 农历模式
            if any(kw in match.group() for kw in ["腊月", "正月", "冬月", "初"]):
                return {
                    "month": None,
                    "day": None,
                    "type": "lunar",
                    "raw": match.group(),
                }

        return None

    def _is_birthday_context(self, context: str) -> bool:
        """判断日期上下文是否确实是生日相关。"""
        birthday_signals = ["生日", "出生", "诞辰", "bday", "birthday"]
        anti_signals = ["会议", "项目", "截止", "ddl", "到期"]

        context_lower = context.lower()
        has_signal = any(s in context_lower for s in birthday_signals)
        has_anti = any(s in context_lower for s in anti_signals)

        # 如果明确是生日信号 → True
        # 如果有反信号（会议等） → False
        # 都不明确 → 保守返回 True（宁可多提取，由置信度处理）
        if has_anti:
            return False
        return True

    def _extract_hobbies(self, text: str) -> List[str]:
        """提取爱好列表。"""
        hobbies = []
        keywords = self.rules.get("hobby_keywords", [])

        for kw in keywords:
            if kw in text:
                hobbies.append(kw)

        # 模式识别："喜欢X"、"爱X"、"热衷于X"、"没事就X"
        # 注意：排除"经常X"（"经常发朋友圈"不是爱好）
        like_pattern = r"(?:喜欢|爱|爱好|热衷于|没事就|平时喜欢)([^\s，。,。；;]{2,8})"
        for match in re.finditer(like_pattern, text):
            hobby = match.group(1).strip()
            # 过滤非爱好短语
            if hobby not in hobbies and len(hobby) >= 2:
                hobbies.append(hobby)

        # 去重：如果 regex 捕获的短语包含了已有关键词，
        # 保留关键词（更准确），丢弃冗余的复合短语
        deduped = []
        for h in hobbies:
            # 如果是关键词词典命中的，直接保留
            if h in keywords:
                deduped.append(h)
            else:
                # regex 捕获的短语，检查是否被已有关键词覆盖
                is_covered = any(
                    kw in h and kw != h
                    for kw in keywords if kw in text
                )
                if not is_covered:
                    deduped.append(h)

        return deduped

    def _extract_events(self, text: str) -> List[Dict]:
        """
        提取关键事件。

        Returns:
            事件列表，每个事件包含 date 和 description。
        """
        events = []
        keywords = self.rules.get("event_keywords", [])

        # 方法1：关键词 + 日期模式
        for kw in keywords:
            if kw not in text:
                continue

            # 找关键词附近的日期
            kw_pos = text.index(kw)
            date = self._find_nearby_date(text, kw_pos)

            events.append({
                "date": date,
                "description": f"提到了：{kw}",
            })

        # 方法2："上次/上回/之前/去年/前年 X月X号" 模式
        last_time_pattern = r"(?:上次|上回|之前|去年|前年|上个月)(\d{1,2})\s*月(?:初|中旬|底|\d{1,2}[号日])?\s*(.+?)(?:[。，,;；\n]|$)"
        for match in re.finditer(last_time_pattern, text):
            events.append({
                "date": f"{match.group(1)}月",
                "description": match.group(2).strip(),
            })

        # 去重：合并相同 description 的事件
        seen = set()
        deduped = []
        for e in events:
            key = e["description"]
            if key not in seen:
                seen.add(key)
                deduped.append(e)

        return deduped

    def _find_nearby_date(self, text: str, position: int) -> Optional[str]:
        """在文本中给定位置附近查找日期。"""
        window = text[max(0, position - 30):min(len(text), position + 30)]
        date_pattern = r"(\d{1,2})\s*月(?:\d{1,2}[号日]|初|中旬|底)"
        match = re.search(date_pattern, window)
        return match.group() if match else None

    def _extract_tags(self, text: str) -> List[str]:
        """根据关键词匹配标签。"""
        tags = []
        tag_map = self.rules.get("tag_keywords", {})

        for tag, keywords in tag_map.items():
            if any(kw in text for kw in keywords):
                tags.append(tag)

        return tags

    # ========== 辅助方法 ==========

    def _cn_num_to_int(self, cn_str: str) -> Optional[int]:
        """中文数字转整数。"""
        mapping = {
            "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
            "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
        }
        # 简单的一位或两位
        if not cn_str:
            return None
        if cn_str in mapping:
            return mapping[cn_str]
        # "十二" → 12, "二十" → 20, "二十三" → 23
        if "十" in cn_str:
            parts = cn_str.split("十")
            tens = mapping.get(parts[0], 1) if parts[0] else 1
            ones = mapping.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
            return tens * 10 + ones
        return None

    def _calc_confidence(self, contact: Dict) -> float:
        """
        计算提取结果的整体置信度。

        策略：每类信息未提取到 → 不扣分；
              提取到 → 加基础分；
              越具体 → 分越高。
        """
        score = 0.3  # 基础分（至少识别出了联系人名）
        max_score = 1.0

        if contact.get("birthday"):
            score += 0.25
        if contact.get("hobbies"):
            score += min(0.15, len(contact["hobbies"]) * 0.05)
        if contact.get("key_events"):
            score += min(0.15, len(contact["key_events"]) * 0.05)
        if contact.get("tags"):
            score += min(0.1, len(contact["tags"]) * 0.03)
        if contact.get("aliases"):
            score += 0.05

        return round(min(score, max_score), 2)


# 便捷函数
def extract_local(text: str, rules_path: str = None) -> Dict:
    """纯本地提取的便捷入口。"""
    extractor = LocalExtractor(rules_path)
    return extractor.extract(text)
