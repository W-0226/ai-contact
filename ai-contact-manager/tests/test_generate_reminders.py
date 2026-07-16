"""
generate_reminders.py 的单元测试

测试覆盖：
- 生日提醒生成（urgent/upcoming/notable/distant 分级）
- 联系建议生成（优先级排序）
- 事件时间线
- 话题建议
- Markdown 报告生成
- None 值安全处理
- 边界情况
"""

import os
import json
import tempfile
import pytest
from generate_reminders import ReminderGenerator, generate_all, generate_markdown_report


# ==================== 生日提醒 ====================

class TestBirthdayReminders:
    """测试生日提醒生成。"""

    def test_solar_birthday_reminder(self, minimal_contacts_data):
        """公历生日提醒。"""
        gen = ReminderGenerator(minimal_contacts_data)
        result = gen.generate()
        birthday_reminders = result["reminders"]["birthday_reminders"]
        assert len(birthday_reminders) >= 1

        # 张三 7月20号，距今天（7月15号）约5天
        zhang = [r for r in birthday_reminders if r["contact"] == "张三"]
        assert len(zhang) == 1
        assert zhang[0]["days_until"] is not None
        assert zhang[0]["status"] in ["urgent", "upcoming", "notable", "distant"]

    def test_birthday_status_classification(self, minimal_contacts_data):
        """生日状态分级正确。"""
        gen = ReminderGenerator(minimal_contacts_data)
        result = gen.generate()
        reminders = result["reminders"]["birthday_reminders"]
        statuses = [r["status"] for r in reminders]
        # 所有状态都应是合法值
        for s in statuses:
            assert s in ["urgent", "upcoming", "notable", "distant", "format_unknown"]

    def test_no_birthday_contacts(self):
        """没有生日信息的联系人不应产生生日提醒。"""
        data = {
            "contacts": [
                {"name": "无名", "birthday": None, "hobbies": [], "key_events": [], "tags": []}
            ]
        }
        gen = ReminderGenerator(data)
        result = gen.generate()
        assert result["reminders"]["birthday_reminders"] == []

    def test_lunar_birthday_handling(self):
        """农历生日处理（格式未知时）。"""
        data = {
            "contacts": [
                {
                    "name": "阿姨",
                    "birthday": {"month": None, "day": None, "type": "lunar", "raw": "腊月初八"},
                    "hobbies": [], "key_events": [], "tags": []
                }
            ]
        }
        gen = ReminderGenerator(data)
        result = gen.generate()
        reminders = result["reminders"]["birthday_reminders"]
        assert len(reminders) == 1
        assert reminders[0]["status"] == "format_unknown"

    def test_sort_order(self, minimal_contacts_data):
        """提醒按紧急程度排序。"""
        gen = ReminderGenerator(minimal_contacts_data)
        result = gen.generate()
        reminders = result["reminders"]["birthday_reminders"]
        if len(reminders) >= 2:
            # 验证排序不会抛出异常
            # urgent < upcoming < notable < distant 按 key 值排序
            status_order = {"urgent": 0, "upcoming": 1, "notable": 2, "distant": 3, "format_unknown": 4}
            for i in range(len(reminders) - 1):
                s1 = status_order[reminders[i]["status"]]
                s2 = status_order[reminders[i + 1]["status"]]
                assert s1 <= s2, f"排序错误: {reminders[i]['status']} 应在 {reminders[i+1]['status']} 之前"


# ==================== 联系建议 ====================

class TestContactSuggestions:
    """测试联系建议生成。"""

    def test_suggestion_with_events(self, minimal_contacts_data):
        """有事件记录的联系人应产生联系建议。"""
        gen = ReminderGenerator(minimal_contacts_data)
        result = gen.generate()
        suggestions = result["reminders"]["contact_suggestions"]
        # 张三有事件，应有建议
        assert len(suggestions) >= 1

    def test_suggestion_without_events(self):
        """没有事件记录的联系人不产生建议。"""
        data = {
            "contacts": [
                {"name": "无名", "birthday": None, "hobbies": [], "key_events": [], "tags": []}
            ]
        }
        gen = ReminderGenerator(data)
        result = gen.generate()
        assert result["reminders"]["contact_suggestions"] == []

    def test_priority_order(self, minimal_contacts_data):
        """按优先级排序（high → medium → low）。"""
        gen = ReminderGenerator(minimal_contacts_data)
        result = gen.generate()
        suggestions = result["reminders"]["contact_suggestions"]
        if len(suggestions) >= 2:
            priority_order = {"high": 0, "medium": 1, "low": 2}
            for i in range(len(suggestions) - 1):
                p1 = priority_order[suggestions[i]["priority"]]
                p2 = priority_order[suggestions[i + 1]["priority"]]
                assert p1 <= p2

    def test_topic_hint_generation(self, minimal_contacts_data):
        """话题建议包含爱好相关提示。"""
        gen = ReminderGenerator(minimal_contacts_data)
        result = gen.generate()
        suggestions = result["reminders"]["contact_suggestions"]
        if suggestions:
            zhang = [s for s in suggestions if s["contact"] == "张三"]
            if zhang:
                assert "跑步" in zhang[0].get("topic_hint", "")


# ==================== 事件时间线 ====================

class TestEventTimeline:
    """测试事件时间线生成。"""

    def test_timeline_generation(self, minimal_contacts_data):
        """时间线包含所有事件。"""
        gen = ReminderGenerator(minimal_contacts_data)
        result = gen.generate()
        timeline = result["reminders"]["event_timeline"]
        # 张三有1个事件
        zhang_events = [e for e in timeline if e["contact"] == "张三"]
        assert len(zhang_events) >= 1

    def test_empty_timeline(self):
        """无事件时时间线为空。"""
        data = {"contacts": [{"name": "无名", "birthday": None, "hobbies": [], "key_events": [], "tags": []}]}
        gen = ReminderGenerator(data)
        result = gen.generate()
        assert result["reminders"]["event_timeline"] == []


# ==================== 话题建议 ====================

class TestTopicSuggestions:
    """测试话题建议生成。"""

    def test_hobby_based_topic(self, minimal_contacts_data):
        """基于爱好的话题建议。"""
        gen = ReminderGenerator(minimal_contacts_data)
        result = gen.generate()
        topics = result["reminders"]["topic_suggestions"]
        zhang = [t for t in topics if t["contact"] == "张三"]
        if zhang:
            has_hobby_topic = any(
                tp["type"] == "hobby" for tp in zhang[0].get("topics", [])
            )
            assert has_hobby_topic, "应包含基于爱好的话题建议"


# ==================== Markdown 报告 ====================

class TestMarkdownReport:
    """测试 Markdown 报告生成。"""

    def test_report_generation(self, minimal_contacts_data):
        """报告可正常生成。"""
        gen = ReminderGenerator(minimal_contacts_data)
        reminders = gen.generate()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_report.md")
            result = generate_markdown_report(minimal_contacts_data, reminders, path)
            assert os.path.exists(result)

            with open(result, "r", encoding="utf-8") as f:
                content = f.read()
            assert "张三" in content
            assert "李四" in content

    def test_report_has_required_sections(self, minimal_contacts_data):
        """报告包含所有必要章节。"""
        gen = ReminderGenerator(minimal_contacts_data)
        reminders = gen.generate()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_report.md")
            generate_markdown_report(minimal_contacts_data, reminders, path)

            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            required_sections = [
                "生日提醒",
                "联系建议",
                "事件时间线",
                "话题建议",
                "联系人概览",
            ]
            for section in required_sections:
                assert section in content, f"缺少章节: {section}"


# ==================== generate_all 便捷函数 ====================

class TestGenerateAll:
    """测试 generate_all 一站式函数。"""

    def test_generate_all_outputs(self, minimal_contacts_data):
        """generate_all 同时生成 JSON 和 Markdown。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = generate_all(minimal_contacts_data, tmpdir)
            assert os.path.exists(result["reminders_json"])
            assert os.path.exists(result["reminders_md"])

            # 验证 JSON 内容
            with open(result["reminders_json"], "r", encoding="utf-8") as f:
                data = json.load(f)
            assert "reminders" in data
            assert "total_contacts" in data


# ==================== None 值安全 ====================

class TestNoneSafety:
    """测试 None 值不会导致崩溃。"""

    def test_none_birthday(self):
        """生日的 month/day 为 None 时安全。"""
        data = {
            "contacts": [
                {
                    "name": "测试",
                    "birthday": {"month": None, "day": None, "type": "lunar", "raw": "腊月初八"},
                    "hobbies": [],
                    "key_events": [],
                    "tags": [],
                }
            ]
        }
        # 不应抛出异常
        gen = ReminderGenerator(data)
        result = gen.generate()
        assert "reminders" in result

    def test_none_event_date(self):
        """事件日期为 None 时不崩溃。"""
        data = {
            "contacts": [
                {
                    "name": "测试",
                    "birthday": None,
                    "hobbies": ["钓鱼"],
                    "key_events": [{"date": None, "description": "测试事件"}],
                    "tags": [],
                }
            ]
        }
        gen = ReminderGenerator(data)
        result = gen.generate()
        # 不应崩溃
        assert "reminders" in result
        # 时间线中的 None 日期应是安全的
        timeline = result["reminders"]["event_timeline"]
        assert len(timeline) >= 1

    def test_empty_contacts_list(self):
        """空联系人列表。"""
        gen = ReminderGenerator({"contacts": []})
        result = gen.generate()
        assert result["total_contacts"] == 0


# ==================== 统计信息 ====================

class TestStats:
    """测试统计信息正确性。"""

    def test_total_contacts_count(self, minimal_contacts_data):
        """联系人总数正确。"""
        gen = ReminderGenerator(minimal_contacts_data)
        result = gen.generate()
        assert result["total_contacts"] == 2

    def test_contacts_with_birthday_count(self, minimal_contacts_data):
        """有生日记录的联系人数量正确。"""
        gen = ReminderGenerator(minimal_contacts_data)
        result = gen.generate()
        assert result["contacts_with_birthday"] == 2
