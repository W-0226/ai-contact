"""
关系确认队列模块 — 数据入库后自动检测模糊项并提供方案

功能：
1. 自动检测：提取完成后扫描所有联系人的模糊/缺失信息
2. 分类判断：对每项模糊信息生成 2-4 个可选方案
3. 生成队列：输出 REVIEW_QUEUE.md 供用户阅读和勾选
4. 时效提醒：标注哪些需要尽快确认（影响后续提醒质量）

触发条件（任一满足即入队）：
- 关系类型不明确（无 tags 且无认识途径特征）
- 生日模糊或缺失
- 价值评级较低但有关键信号（如 CTO/CEO 但信息空白）
- 长时间未联系但原因不明（缺上下文判断）
- 有潜在商业价值但不知道如何切入
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class ReviewQueue:
    """关系确认队列生成器。"""

    def __init__(self):
        self.queue = []
        self.detected_at = datetime.now()

    def scan(self, contacts: List[Dict], relationship_analysis: Optional[Dict] = None) -> List[Dict]:
        """
        扫描所有联系人，生成待确认项。

        Args:
            contacts: 提取的联系人列表
            relationship_analysis: 关系分析结果（可选，用于价值上下文）

        Returns:
            待确认项列表，每项包含 question/options/reason/urgency
        """
        self.queue = []
        self.detected_at = datetime.now()

        # 构建价值映射（如果有分析结果）
        scored_map = {}
        if relationship_analysis:
            for c in relationship_analysis.get("scored_contacts", []):
                scored_map[c.get("name", "")] = c.get("relationship_score", {})

        for contact in contacts:
            name = contact.get("name", "未知")
            if name == "未知联系人":
                continue

            score = scored_map.get(name, {})
            self._check_relationship_type(contact, score)
            self._check_birthday(contact)
            self._check_high_value_blank(contact, score)
            self._check_dormant_no_context(contact, score)
            self._check_icebreaker_blocked(contact, score)
            self._check_missing_basics(contact)

        return self.queue

    # ========== 各项检测 ==========

    def _check_relationship_type(self, contact: Dict, score: Dict):
        """
        检测：关系类型不明确。
        触发条件：无标签 且 备注中无明确关系词。
        """
        tags = contact.get("tags", [])
        notes = contact.get("notes", "")
        rel_indicators = ["同学", "同事", "室友", "邻居", "亲戚", "朋友",
                          "认识", "客户", "合作", "教练", "老师", "导师"]

        has_tags = len(tags) > 0
        has_rel_indicator = any(ind in notes for ind in rel_indicators)

        if not has_tags and not has_rel_indicator:
            self.queue.append({
                "contact": contact["name"],
                "category": "关系类型",
                "question": f"「{contact['name']}」和你是什么关系？",
                "options": [
                    "📌 工作关系（同事/客户/合作伙伴）",
                    "📌 私人朋友（同学/邻居/兴趣圈子）",
                    "📌 一面之缘（峰会/活动/别人介绍）",
                    "📌 亲戚/家人",
                    "✏️ 其他（请在下方补充）",
                ],
                "reason": "未提取到关系标签或认识途径，这会影响联系频率和话题建议的准确性",
                "urgency": "medium",
                "impact": "影响关系亲密度评分和联系建议的优先级",
            })

    def _check_birthday(self, contact: Dict):
        """
        检测：生日缺失或模糊。
        """
        birthday = contact.get("birthday")
        if not birthday:
            self.queue.append({
                "contact": contact["name"],
                "category": "生日信息",
                "question": f"「{contact['name']}」的生日是什么时候？",
                "options": [
                    "📅 我知道，补充如下：___月___日（公历/农历）",
                    "📅 暂时不知道，下次聊天时问问",
                    "📅 这不重要，跳过",
                ],
                "reason": "缺少生日会导致无法生成生日提醒，错过重要的关系维护时机",
                "urgency": "low",
                "impact": "影响生日提醒和节日关怀",
            })
        elif birthday.get("type") == "lunar" or birthday.get("type") == "unknown":
            self.queue.append({
                "contact": contact["name"],
                "category": "生日信息",
                "question": f"「{contact['name']}」的生日「{birthday.get('raw','')}」需要确认",
                "options": [
                    f"✅ 确认为农历：{birthday.get('raw','')}",
                    f"🔄 实际是公历：需要补充具体日期",
                    "📅 不确定，暂时保留",
                ],
                "reason": "农历日期每年对应的公历日期不同，确认后可以准确计算提醒时间",
                "urgency": "low",
                "impact": "影响提醒日期的准确性",
            })

    def _check_high_value_blank(self, contact: Dict, score: Dict):
        """
        检测：高价值信号但信息空白。
        例如：CTO/CEO/创始人 但无爱好、无生日、无事件。
        """
        notes = contact.get("notes", "")
        high_signals = ["CEO", "CTO", "创始人", "合伙人", "总监", "VP"]

        has_signal = any(s in notes for s in high_signals)
        has_info = bool(contact.get("hobbies") or contact.get("birthday") or contact.get("key_events"))

        if has_signal and not has_info:
            self.queue.append({
                "contact": contact["name"],
                "category": "高价值信息补全",
                "question": f"「{contact['name']}」有高价值身份（{', '.join([s for s in high_signals if s in notes])}），但个人信息几乎空白",
                "options": [
                    "✨ 值得花时间了解，标记为「重点跟进」",
                    "🔍 先搜索TA的公开信息（领英/公司官网/新闻）",
                    "⏰ 下次有合适机会时自然了解",
                    "💤 暂时不处理，保持观察",
                ],
                "reason": "高价值人脉缺乏基本信息会导致错过最佳联系时机，或见面时无话可聊",
                "urgency": "high",
                "impact": "影响潜在价值评估和破冰话题质量",
            })

    def _check_dormant_no_context(self, contact: Dict, score: Dict):
        """
        检测：长时间未联系且缺少上下文判断。
        """
        quality = score.get("contact_quality", 0)
        info = score.get("info_completeness", 0)

        # 联系质量低 + 信息少 → 无法判断是自然疏远还是有原因
        if quality < 10 and info < 15:
            self.queue.append({
                "contact": contact["name"],
                "category": "断联原因",
                "question": f"「{contact['name']}」已较长时间未联系，需要判断原因",
                "options": [
                    "📌 自然疏远（无共同场景/话题了）— 可降低维护频率",
                    "📌 暂时忙碌（双方都忙没顾上）— 建议近期补联系",
                    "📌 关系降温（之前有过不愉快/对方冷淡）— 观察或放手",
                    "🤷 不确定，保持现状",
                ],
                "reason": "无法自动判断断联原因，错误的判断会导致不合时宜的联系或错过修复机会",
                "urgency": "medium",
                "impact": "影响联系建议的准确性和破冰话术的有效性",
            })

    def _check_icebreaker_blocked(self, contact: Dict, score: Dict):
        """
        检测：想联系但不知从何切入。
        """
        notes = contact.get("notes", "")
        blocked_signals = ["不知道", "不知", "想约", "不知道怎么", "不知道从"]

        if any(s in notes for s in blocked_signals):
            self.queue.append({
                "contact": contact["name"],
                "category": "破冰障碍",
                "question": f"你想联系「{contact['name']}」但不知道从什么话题切入，需要帮助判断",
                "options": [
                    "💼 以行业动态切入 — 关注TA所在的领域新闻",
                    "🎯 以共同联系人切入 — 通过介绍人/共同朋友牵线",
                    "📚 以知识请教切入 — 以TA的专业领域请教名义破冰",
                    "☕ 直接邀约 — 简单直接约咖啡/午饭",
                    "⏸️ 暂时不联系，等合适时机",
                ],
                "reason": "用户在备注中明确了联系意愿但缺乏切入策略",
                "urgency": "high",
                "impact": "直接影响能否激活这层关系",
            })

    def _check_missing_basics(self, contact: Dict):
        """
        检测：基础信息几乎完全缺失。
        """
        has_birthday = bool(contact.get("birthday"))
        has_hobbies = bool(contact.get("hobbies"))
        has_events = bool(contact.get("key_events"))

        basics_count = sum([has_birthday, has_hobbies, has_events])

        if basics_count == 0:
            self.queue.append({
                "contact": contact["name"],
                "category": "信息补全",
                "question": f"「{contact['name']}」几乎没有任何个人信息记录",
                "options": [
                    "🔍 翻看聊天记录补充信息",
                    "👀 翻TA的朋友圈/社交媒体了解",
                    "💬 下次聊天时有意识地了解",
                    "💤 这个联系人不太重要，保持现状",
                ],
                "reason": "信息量为零的人脉无法有效维护，建议至少补充一项基本信息",
                "urgency": "medium",
                "impact": "影响所有后续分析的准确性",
            })

    # ========== 生成 Markdown 队列文件 ==========

    def generate_markdown(self, output_path: str) -> str:
        """
        生成 REVIEW_QUEUE.md 文件。

        Args:
            output_path: 输出文件路径

        Returns:
            文件路径
        """
        if not self.queue:
            # 即使没有待确认项也生成一个空队列
            lines = _build_empty_queue()
        else:
            lines = _build_queue_markdown(self.queue, self.detected_at)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"关系确认队列 → {output_path}（{len(self.queue)} 项）")
        return output_path


def _build_queue_markdown(queue: List[Dict], detected_at: datetime) -> List[str]:
    """构建队列 Markdown 内容。"""
    lines = []
    lines.append(f"# 📋 关系确认队列")
    lines.append(f"")
    lines.append(f"**生成时间**：{detected_at.isoformat()}")
    lines.append(f"**待确认项**：{len(queue)} 项")
    lines.append(f"")
    lines.append(f"> 📖 使用说明：阅读以下问题，在每个问题的选项中勾选你的答案。")
    lines.append(f"> 确认后将答案告诉 AI 助手，TA 会更新联系人档案。")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    # 按紧急程度排序
    urgency_order = {"high": 0, "medium": 1, "low": 2}
    sorted_queue = sorted(queue, key=lambda q: urgency_order.get(q.get("urgency", "low"), 99))

    # 紧急提示
    high_items = [q for q in sorted_queue if q.get("urgency") == "high"]
    if high_items:
        lines.append(f"## ⚠️ 需要尽快处理（{len(high_items)} 项）")
        lines.append(f"")
        lines.append(f"> 以下项目影响较大，建议优先确认。")
        lines.append(f"")

    for i, item in enumerate(sorted_queue, 1):
        urgency_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(item.get("urgency", "low"), "")
        lines.append(f"### {urgency_icon} #{i} — {item['category']}：{item['contact']}")
        lines.append(f"")
        lines.append(f"**❓ {item['question']}**")
        lines.append(f"")
        lines.append(f"**可选方案**：")
        for j, option in enumerate(item.get("options", []), 1):
            lines.append(f"- [ ] {option}")
        lines.append(f"")
        lines.append(f"*原因：{item.get('reason', '')}*")
        lines.append(f"*影响：{item.get('impact', '')}*")
        lines.append(f"")

    lines.append(f"---")
    lines.append(f"")
    lines.append(f"## 📊 确认进度")
    lines.append(f"")
    lines.append(f"| 状态 | 数量 |")
    lines.append(f"|------|:----:|")
    lines.append(f"| ✅ 已确认 | 0 / {len(queue)} |")
    lines.append(f"| ⏳ 待确认 | {len(queue)} |")
    lines.append(f"")
    lines.append(f"> 确认后请联系 AI 助手更新档案：")
    lines.append(f"> 「我已确认 REVIEW_QUEUE.md 中的第 X 项，答案如下：...」")
    lines.append(f"")

    return lines


def _build_empty_queue() -> List[str]:
    """构建空队列提示。"""
    return [
        f"# 📋 关系确认队列",
        f"",
        f"**生成时间**：{datetime.now().isoformat()}",
        f"**待确认项**：0 项",
        f"",
        f"> ✅ 所有联系人的关系信息足够清晰，无需确认。",
        f"",
    ]
