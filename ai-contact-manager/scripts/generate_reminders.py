# -*- coding: utf-8 -*-
"""
提醒生成器 — 基于结构化联系人数据，
生成生日提醒、联系建议、关系价值评估、断联预警等。

输出格式：JSON 数据 + Markdown 可读报告。
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class ReminderGenerator:
    """联系提醒生成器。"""

    DAYS_THRESHOLD_WARNING = 30     # 30天内联系预警
    DAYS_THRESHOLD_SUGGEST = 90     # 90天内建议联系

    def __init__(self, contacts_data: Dict):
        """
        初始化提醒生成器。

        Args:
            contacts_data: 提取引擎返回的 contacts 数据，
                          格式为 {"contacts": [...]}
        """
        self.contacts = contacts_data.get("contacts", [])
        self.today = datetime.now().date()

    def generate(self, max_reminders: int = 10) -> Dict:
        """
        生成提醒数据。

        Returns:
            包含 reminders 列表和统计信息的字典。
        """
        reminders = {
            "birthday_reminders": self._gen_birthday_reminders(),
            "contact_suggestions": self._gen_contact_suggestions(),
            "event_timeline": self._gen_event_timeline(),
            "topic_suggestions": self._gen_topic_suggestions(),
        }

        # 关系价值分析
        try:
            from relationship_analyzer import RelationshipAnalyzer
            analyzer = RelationshipAnalyzer(self.today)
            relationship_analysis = analyzer.analyze(self.contacts)
        except ImportError:
            relationship_analysis = None

        return {
            "reminders": reminders,
            "relationship_analysis": relationship_analysis,
            "generated_at": datetime.now().isoformat(),
            "total_contacts": len(self.contacts),
            "contacts_with_birthday": len([c for c in self.contacts if c.get("birthday")]),
        }

    # ========== 生日提醒 ==========

    def _gen_birthday_reminders(self) -> List[Dict]:
        """生成生日提醒列表。"""
        reminders = []

        for contact in self.contacts:
            birthday = contact.get("birthday")
            if not birthday:
                continue

            month = birthday.get("month")
            day = birthday.get("day")
            birthday_type = birthday.get("type", "solar")

            if month is None or day is None:
                # 农历或格式不完整的日期，仅记录
                reminders.append({
                    "contact": contact["name"],
                    "birthday_raw": birthday.get("raw", "未知"),
                    "birthday_type": birthday_type,
                    "days_until": None,
                    "status": "format_unknown",
                    "suggestion": "请手动确认具体日期后设置提醒",
                })
                continue

            # 计算距今天数
            try:
                days_until = self._days_until_birthday(month, day)
            except ValueError:
                continue

            # 分类
            if days_until <= 7:
                status = "urgent"       # 一周内
                suggestion = f"🎂 生日在即！只剩 {days_until} 天，请尽快准备"
            elif days_until <= self.DAYS_THRESHOLD_WARNING:
                status = "upcoming"    # 30天内
                suggestion = f"📅 生日将至，还有 {days_until} 天，可以开始准备了"
            elif days_until <= 90:
                status = "notable"     # 90天内
                suggestion = f"还有 {days_until} 天，可以标记一下"
            else:
                status = "distant"
                suggestion = f"距离生日还有 {days_until} 天，可以设置年度提醒"

            reminders.append({
                "contact": contact["name"],
                "birthday": f"{month}月{day}日",
                "birthday_type": birthday_type,
                "days_until": days_until,
                "status": status,
                "suggestion": suggestion,
            })

        # 按紧急程度和距今日排序
        reminders.sort(key=lambda r: (
            0 if r["status"] == "urgent" else
            1 if r["status"] == "upcoming" else
            2 if r["status"] == "notable" else 3,
            r.get("days_until") if r.get("days_until") is not None else 999
        ))

        return reminders

    def _days_until_birthday(self, month: int, day: int) -> int:
        """计算到下一个生日的天数。"""
        try:
            next_birthday = datetime(self.today.year, month, day).date()
        except ValueError:
            # 处理 2月29日
            if month == 2 and day == 29:
                next_birthday = datetime(self.today.year, 2, 28).date()
            else:
                raise

        if next_birthday < self.today:
            # 今年的生日已过，算明年的
            try:
                next_birthday = datetime(self.today.year + 1, month, day).date()
            except ValueError:
                if month == 2 and day == 29:
                    next_birthday = datetime(self.today.year + 1, 2, 28).date()

        return (next_birthday - self.today).days

    # ========== 联系建议 ==========

    def _gen_contact_suggestions(self) -> List[Dict]:
        """生成联系建议（基于最近一次关键事件）。"""
        suggestions = []

        for contact in self.contacts:
            events = contact.get("key_events", [])
            if not events:
                continue

            # 找出最近的事件
            latest_event = None
            for event in events:
                event_date = event.get("date")
                if not event_date:
                    continue
                # 简单判断：日期越往后越近
                if latest_event is None or event_date > latest_event.get("date", ""):
                    latest_event = event

            if not latest_event:
                continue

            days_since = self._estimate_days_since(latest_event.get("date", ""))
            if days_since is None:
                continue

            # 根据时间间隔给出建议
            if days_since > self.DAYS_THRESHOLD_SUGGEST:
                priority = "high"
                suggestion = f"已 {days_since} 天未联系，建议近期主动问候"
            elif days_since > self.DAYS_THRESHOLD_WARNING:
                priority = "medium"
                suggestion = f"已 {days_since} 天，可以找机会聊聊"
            else:
                priority = "low"
                suggestion = f"最近有联系（{days_since} 天前），保持即可"

            # 基于兴趣生成话题
            topics = contact.get("hobbies", [])
            topic_hint = ""
            if topics:
                topic_hint = f"可以从{topics[0]}这个话题切入"

            suggestions.append({
                "contact": contact["name"],
                "last_event": latest_event.get("description", ""),
                "last_event_date": latest_event.get("date", ""),
                "days_since_last_contact": days_since,
                "priority": priority,
                "suggestion": suggestion,
                "topic_hint": topic_hint,
            })

        # 按优先级排序
        suggestions.sort(key=lambda s: (
            0 if s["priority"] == "high" else
            1 if s["priority"] == "medium" else 2,
        ))

        return suggestions

    def _estimate_days_since(self, date_str: str) -> Optional[int]:
        """粗略估计距今天数（仅用于联系提醒排序）。"""
        import re

        # 带年份格式：2026年5月、2025年12月
        match = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月", date_str)
        if match:
            year, month = int(match.group(1)), int(match.group(2))
            try:
                event_date = datetime(year, month, 15).date()
                return (self.today - event_date).days
            except ValueError:
                return None

        # 尝试解析 X月X号/日
        match = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})", date_str)
        if match:
            month, day = int(match.group(1)), int(match.group(2))
            try:
                event_date = datetime(self.today.year, month, day).date()
                if event_date > self.today:
                    # 可能是去年的事件
                    event_date = datetime(self.today.year - 1, month, day).date()
                return (self.today - event_date).days
            except ValueError:
                return None

        # X月初/中旬/底
        match = re.search(r"(\d{1,2})\s*月初", date_str)
        if match:
            month = int(match.group(1))
            event_date = datetime(self.today.year, month, 1).date()
            if event_date > self.today:
                event_date = datetime(self.today.year - 1, month, 1).date()
            return (self.today - event_date).days

        match = re.search(r"(\d{1,2})\s*月中", date_str)
        if match:
            month = int(match.group(1))
            event_date = datetime(self.today.year, month, 15).date()
            if event_date > self.today:
                event_date = datetime(self.today.year - 1, month, 15).date()
            return (self.today - event_date).days

        match = re.search(r"(\d{1,2})\s*月底", date_str)
        if match:
            month = int(match.group(1))
            event_date = datetime(self.today.year, month, 28).date()
            if event_date > self.today:
                event_date = datetime(self.today.year - 1, month, 28).date()
            return (self.today - event_date).days

        # 仅月份：5月、12月（无具体日期，默认月中）
        match = re.search(r"(\d{1,2})\s*月", date_str)
        if match:
            month = int(match.group(1))
            event_date = datetime(self.today.year, month, 15).date()
            if event_date > self.today:
                event_date = datetime(self.today.year - 1, month, 15).date()
            return (self.today - event_date).days

        return None

    # ========== 事件时间线 ==========

    def _gen_event_timeline(self) -> List[Dict]:
        """生成关键事件时间线。"""
        timeline = []

        for contact in self.contacts:
            for event in contact.get("key_events", []):
                timeline.append({
                    "contact": contact["name"],
                    "date": event.get("date") or "",
                    "description": event.get("description") or "",
                })

        # 按日期排序（字符串排序，粗略但实用）
        timeline.sort(key=lambda e: e["date"])

        return timeline

    # ========== 话题建议 ==========

    def _gen_topic_suggestions(self) -> List[Dict]:
        """基于兴趣和标签生成话题建议。"""
        suggestions = []

        for contact in self.contacts:
            hobbies = contact.get("hobbies", [])
            events = contact.get("key_events", [])
            tags = contact.get("tags", [])

            if not hobbies and not events:
                continue

            topics = []

            # 基于爱好
            for hobby in hobbies[:3]:
                topics.append({
                    "type": "hobby",
                    "content": f"聊聊{hobby}相关的话题",
                })

            # 基于最近事件跟进
            if events:
                latest = events[-1]
                topics.append({
                    "type": "follow_up",
                    "content": f"跟进上次聊到的：{latest.get('description', '')}",
                })

            suggestions.append({
                "contact": contact["name"],
                "topics": topics,
            })

        return suggestions


# ========== Markdown 报告生成 ==========

def generate_markdown_report(contacts_data: Dict, reminders_data: Dict, output_path: str):
    """
    生成人类可读的 Markdown 联系提醒报告。

    Args:
        contacts_data: 提取的联系人数据
        reminders_data: 提醒生成器返回的数据
        output_path: 输出文件路径
    """
    contacts = contacts_data.get("contacts", [])
    reminders = reminders_data.get("reminders", {})

    lines = []
    lines.append(f"# 📇 AI人脉关系管家 — 联系提醒报告")
    lines.append(f"")
    lines.append(f"**生成时间**：{reminders_data.get('generated_at', datetime.now().isoformat())}")
    lines.append(f"**联系人总数**：{reminders_data.get('total_contacts', len(contacts))}")
    lines.append(f"**有生日记录**：{reminders_data.get('contacts_with_birthday', 0)} 人")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    # 一、生日提醒
    lines.append(f"## 🎂 近期生日提醒")
    lines.append(f"")
    birthday_reminders = reminders.get("birthday_reminders", [])
    if birthday_reminders:
        urgent = [r for r in birthday_reminders if r.get("status") == "urgent"]
        upcoming = [r for r in birthday_reminders if r.get("status") == "upcoming"]
        notable = [r for r in birthday_reminders if r.get("status") == "notable"]

        if urgent:
            lines.append(f"### ⚠️ 紧急（7天内）")
            lines.append(f"")
            lines.append(f"| 联系人 | 生日 | 距今天数 | 建议 |")
            lines.append(f"|--------|------|----------|------|")
            for r in urgent:
                lines.append(f"| {r['contact']} | {r.get('birthday', r.get('birthday_raw', '-'))} | {r.get('days_until', '?')}天 | {r['suggestion']} |")
            lines.append(f"")

        if upcoming:
            lines.append(f"### 📅 即将到来（30天内）")
            lines.append(f"")
            lines.append(f"| 联系人 | 生日 | 距今天数 | 建议 |")
            lines.append(f"|--------|------|----------|------|")
            for r in upcoming:
                lines.append(f"| {r['contact']} | {r.get('birthday', r.get('birthday_raw', '-'))} | {r.get('days_until', '?')}天 | {r['suggestion']} |")
            lines.append(f"")

        if notable:
            lines.append(f"### 📌 值得关注（90天内）")
            lines.append(f"")
            lines.append(f"| 联系人 | 生日 | 距今天数 |")
            lines.append(f"|--------|------|----------|")
            for r in notable:
                lines.append(f"| {r['contact']} | {r.get('birthday', r.get('birthday_raw', '-'))} | {r.get('days_until', '?')}天 |")
            lines.append(f"")
    else:
        lines.append(f"> 未发现可识别的生日信息。")
        lines.append(f"")

    # 二、联系建议
    lines.append(f"## 📞 联系建议")
    lines.append(f"")
    contact_suggestions = reminders.get("contact_suggestions", [])
    if contact_suggestions:
        lines.append(f"| 联系人 | 上次联系 | 距今天数 | 优先级 | 建议 | 话题切入 |")
        lines.append(f"|--------|----------|----------|--------|------|----------|")
        for s in contact_suggestions[:10]:
            priority_icon = "🔴" if s["priority"] == "high" else "🟡" if s["priority"] == "medium" else "🟢"
            lines.append(
                f"| {s['contact']} | {s.get('last_event_date', '-')} "
                f"| {s['days_since_last_contact']}天 | {priority_icon} {s['priority']} "
                f"| {s['suggestion']} | {s.get('topic_hint', '-')} |"
            )
        lines.append(f"")
    else:
        lines.append(f"> 暂无联系记录可供分析。")
        lines.append(f"")

    # 三、事件时间线
    lines.append(f"## 📅 关键事件时间线")
    lines.append(f"")
    timeline = reminders.get("event_timeline", [])
    if timeline:
        lines.append(f"| 日期 | 联系人 | 事件 |")
        lines.append(f"|------|--------|------|")
        for event in timeline[:20]:
            lines.append(f"| {event.get('date', '-')} | {event['contact']} | {event.get('description', '-')} |")
        lines.append(f"")
    else:
        lines.append(f"> 未发现关键事件记录。")
        lines.append(f"")

    # 四、话题建议
    lines.append(f"## 💬 沟通话题建议")
    lines.append(f"")
    topic_suggestions = reminders.get("topic_suggestions", [])
    if topic_suggestions:
        for s in topic_suggestions:
            lines.append(f"### {s['contact']}")
            for topic in s.get("topics", []):
                icon = "🎯" if topic["type"] == "follow_up" else "💡"
                lines.append(f"- {icon} {topic['content']}")
            lines.append(f"")
    else:
        lines.append(f"> 暂无话题建议。")
        lines.append(f"")

    # 五、联系人概览
    lines.append(f"---")
    lines.append(f"")
    lines.append(f"## 📋 联系人概览")
    lines.append(f"")

    for contact in contacts:
        lines.append(f"### {contact.get('name', '-')}")
        lines.append(f"")
        lines.append(f"- **别名**：{', '.join(contact.get('aliases', [])) or '无'}")
        birthday = contact.get("birthday")
        if birthday:
            raw_bday = birthday.get('raw') or f"{birthday.get('month')}月{birthday.get('day')}日"
            lines.append(f"- **生日**：{raw_bday}（{birthday.get('type', 'unknown')}）")
        else:
            lines.append(f"- **生日**：未知")
        lines.append(f"- **爱好**：{', '.join(contact.get('hobbies', [])) or '未记录'}")
        lines.append(f"- **标签**：{', '.join(contact.get('tags', [])) or '无'}")
        lines.append(f"- **关键事件**：")
        for event in contact.get("key_events", []):
            lines.append(f"  - [{event.get('date', '?')}] {event.get('description', '')}")
        if not contact.get("key_events"):
            lines.append(f"  - 无记录")
        lines.append(f"- **置信度**：{contact.get('confidence', 'N/A')}")
        lines.append(f"- **数据来源**：{contact.get('source', 'unknown')}")
        notes = contact.get("notes", "")
        if notes and notes != contact.get("name", ""):
            lines.append(f"- **备注**：{notes[:200]}")
        lines.append(f"")

    # 六、关系价值分析
    relationship_analysis = reminders_data.get("relationship_analysis")
    if relationship_analysis:
        _append_relationship_section(lines, relationship_analysis)

    # 写入文件
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


# ========== 关系分析章节（Markdown） ==========

def _append_relationship_section(lines: list, analysis: dict):
    """在报告中追加关系价值分析和断联预警章节。"""
    summary = analysis.get("summary", {})
    dormant = analysis.get("dormant_alerts", [])
    ranking = analysis.get("value_ranking", [])

    lines.append(f"---")
    lines.append(f"")
    lines.append(f"## 📊 关系价值分析")
    lines.append(f"")

    # 统计概览
    high = summary.get("high_value", 0)
    medium = summary.get("medium_value", 0)
    low = summary.get("low_value", 0)
    lines.append(f"| 价值等级 | 人数 | 说明 |")
    lines.append(f"|----------|:----:|------|")
    lines.append(f"| 🔴 高价值（≥70分） | {high} | 信息完整、关系密切或商业价值高，需重点维护 |")
    lines.append(f"| 🟡 中等价值（40-69） | {medium} | 有一定价值但信息或联系频率不足 |")
    lines.append(f"| 🟢 低价值（<40分） | {low} | 信息匮乏、疏于联系或价值有限 |")
    lines.append(f"")

    # 价值排行榜（Top 10）
    if ranking:
        lines.append(f"### 🏆 关系价值排行榜（Top 10）")
        lines.append(f"")
        lines.append(f"| 排名 | 联系人 | 总分 | 信息 | 亲密 | 联系 | 潜力 | 等级 |")
        lines.append(f"|:----:|--------|:----:|:----:|:----:|:----:|:----:|:----:|")
        for i, c in enumerate(ranking[:10], 1):
            s = c.get("relationship_score", {})
            level_icon = "🔴" if s.get("level") == "high" else "🟡" if s.get("level") == "medium" else "🟢"
            lines.append(
                f"| {i} | {c['name']} | **{s.get('total', 0)}** | "
                f"{s.get('info_completeness', 0)} | {s.get('intimacy', 0)} | "
                f"{s.get('contact_quality', 0)} | {s.get('potential_value', 0)} | "
                f"{level_icon} |"
            )
        lines.append(f"")

        # 亮点/弱点
        for c in ranking[:5]:
            s = c.get("relationship_score", {})
            highlights = s.get("highlights", [])
            weaknesses = s.get("weaknesses", [])
            if highlights or weaknesses:
                lines.append(f"**{c['name']}**：{' '.join('✅'+h for h in highlights)} {' '.join('⚠️'+w for w in weaknesses)}")
        lines.append(f"")

    # 断联预警
    lines.append(f"---")
    lines.append(f"")
    lines.append(f"## 🚨 断联预警")
    lines.append(f"")

    if dormant:
        lines.append(f"共 **{len(dormant)}** 人处于非活跃状态（{summary.get('zombie_count',0)} 人从未联系过）：")
        lines.append(f"")

        for alert in dormant:
            status_icons = {
                "cooling": "🟡", "cold": "🟠", "frozen": "🔴", "zombie": "💀"
            }
            icon = status_icons.get(alert["status"], "❓")
            days = alert.get("days_since_contact")
            days_str = f"{days}天" if days is not None else "从未联系"

            lines.append(f"### {icon} {alert['name']} — {alert['status_label']}（{days_str}）")
            lines.append(f"")

            # 关系价值
            value_level = alert.get("value_level", "low")
            value_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(value_level, "")
            lines.append(f"- **关系价值**：{value_icon} {value_level}")

            # 可放手？
            if alert.get("should_let_go"):
                lines.append(f"- **💤 建议考量**：此关系价值低且长期未联系，可考虑放手，减少维护成本")
            lines.append(f"")

            # 原因诊断
            reasons = alert.get("reasons", [])
            if reasons:
                lines.append(f"**可能原因**：")
                for r in reasons:
                    conf_bar = "█" * int(r["confidence"] * 10) + "░" * (10 - int(r["confidence"] * 10))
                    lines.append(f"- {r['reason']} （置信度 {conf_bar} {r['confidence']:.0%}）")
                lines.append(f"")

            # 行动方案
            plan = alert.get("action_plan", {})
            if plan:
                urgency_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
                urgency = urgency_icons.get(plan.get("urgency", "low"), "")
                lines.append(f"**建议方案**（紧急度：{urgency} {plan.get('urgency','low')}）：")
                lines.append(f"- 📌 **动作**：{plan.get('recommended_action', '')}")
                lines.append(f"- 💬 **破冰话术**：{plan.get('icebreaker', '')}")
                lines.append(f"- ⏰ **时机**：{plan.get('timing', '近期')}")
                if plan.get("fallback"):
                    lines.append(f"- 🔄 **备选**：{plan['fallback']}")
                lines.append(f"")
    else:
        lines.append(f"> ✅ 所有联系人均处于活跃状态，暂无需预警。")
        lines.append(f"")


# 便捷函数
def generate_all(contacts_data: Dict, output_dir: str, max_reminders: int = 10):
    """一键生成所有提醒输出（JSON + Markdown）。"""
    os.makedirs(output_dir, exist_ok=True)

    generator = ReminderGenerator(contacts_data)
    reminders_data = generator.generate(max_reminders=max_reminders)

    # JSON 输出
    json_path = os.path.join(output_dir, "reminders.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(reminders_data, f, ensure_ascii=False, indent=2)

    # Markdown 输出
    md_path = os.path.join(output_dir, "reminders.md")
    generate_markdown_report(contacts_data, reminders_data, md_path)

    return {
        "reminders_json": json_path,
        "reminders_md": md_path,
    }
