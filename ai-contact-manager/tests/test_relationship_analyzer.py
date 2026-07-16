"""
relationship_analyzer.py 的单元测试
"""

import pytest
from datetime import datetime, timedelta
from relationship_analyzer import RelationshipAnalyzer


@pytest.fixture
def analyzer():
    return RelationshipAnalyzer(today=datetime(2026, 7, 15))


@pytest.fixture
def sample_contacts():
    return [
        {
            "name": "老王",
            "birthday": {"month": 3, "day": 15, "type": "solar"},
            "hobbies": ["钓鱼", "乒乓球"],
            "key_events": [{"date": "2026年7月", "description": "聊跨境电商"}],
            "tags": ["已婚", "有孩子"],
            "notes": "老王，大学同学，喜欢钓鱼",
            "confidence": 0.9,
        },
        {
            "name": "赵总",
            "birthday": None,
            "hobbies": [],
            "key_events": [],
            "tags": [],
            "notes": "赵总，上次峰会认识，做AI芯片的CTO。加了微信但一直没联系",
            "confidence": 0.35,
        },
        {
            "name": "李明",
            "birthday": None,
            "hobbies": ["打篮球"],
            "key_events": [{"date": "2025年12月", "description": "换工作"}],
            "tags": ["程序员", "单身"],
            "notes": "李明，大学同学，程序员",
            "confidence": 0.8,
        },
    ]


class TestValueScoring:
    """关系价值评分测试。"""

    def test_high_value_contact(self, analyzer, sample_contacts):
        """信息完整的联系人应获得高分。"""
        score = analyzer._score_contact(sample_contacts[0])  # 老王
        assert score["total"] >= 60
        assert score["level"] in ("high", "medium")

    def test_low_value_contact(self, analyzer, sample_contacts):
        """信息稀疏的联系人应获得低分。"""
        score = analyzer._score_contact(sample_contacts[1])  # 赵总
        assert score["total"] < 40
        assert score["level"] == "low"

    def test_info_completeness(self, analyzer, sample_contacts):
        """有生日的联系人信息完整度更高。"""
        score_wang = analyzer._score_contact(sample_contacts[0])
        score_zhao = analyzer._score_contact(sample_contacts[1])
        assert score_wang["info_completeness"] > score_zhao["info_completeness"]

    def test_score_range(self, analyzer, sample_contacts):
        """所有评分在 0-100 范围内。"""
        for c in sample_contacts:
            s = analyzer._score_contact(c)
            assert 0 <= s["total"] <= 100

    def test_potential_value_signals(self, analyzer):
        """CEO/创业等高价值信号应提升潜在价值分。"""
        contact = {"name": "CEO", "notes": "某公司CEO，去年融资了天使轮", "hobbies": [], "key_events": [], "tags": []}
        score = analyzer._score_contact(contact)
        assert score["potential_value"] >= 10


class TestDormantAnalysis:
    """断联分析测试。"""

    def test_dormant_detection(self, analyzer, sample_contacts):
        """应正确识别断联联系人。"""
        result = analyzer.analyze(sample_contacts)
        dormant = result["dormant_alerts"]
        # 赵总应该是僵尸（从未联系）
        zombie = [d for d in dormant if d["name"] == "赵总"]
        assert len(zombie) == 1
        assert zombie[0]["status"] == "zombie"

    def test_active_contact_no_alert(self, analyzer, sample_contacts):
        """活跃联系人不产生断联预警。"""
        result = analyzer.analyze(sample_contacts)
        dormant_names = [d["name"] for d in result["dormant_alerts"]]
        # 老王最近有联系（2026年7月），不应在预警列表中
        assert "老王" not in dormant_names

    def test_zombie_reason(self, analyzer, sample_contacts):
        """僵尸人脉应诊断出合理原因。"""
        result = analyzer.analyze(sample_contacts)
        zombie = [d for d in result["dormant_alerts"] if d["name"] == "赵总"]
        assert len(zombie[0]["reasons"]) >= 1

    def test_action_plan_generated(self, analyzer, sample_contacts):
        """断联联系人应有行动方案。"""
        result = analyzer.analyze(sample_contacts)
        for alert in result["dormant_alerts"]:
            assert "action_plan" in alert
            assert alert["action_plan"]["recommended_action"]

    def test_should_let_go(self, analyzer, sample_contacts):
        """极低价值僵尸人脉应建议放手。"""
        result = analyzer.analyze(sample_contacts)
        zombie = [d for d in result["dormant_alerts"] if d["name"] == "赵总"]
        assert zombie[0]["should_let_go"] is True


class TestSummary:
    """汇总统计测试。"""

    def test_summary_counts(self, analyzer, sample_contacts):
        """统计数字应正确。"""
        result = analyzer.analyze(sample_contacts)
        summary = result["summary"]
        assert summary["total_contacts"] == 3
        assert summary["zombie_count"] >= 1

    def test_value_distribution(self, analyzer, sample_contacts):
        """价值分布应合理。"""
        result = analyzer.analyze(sample_contacts)
        summary = result["summary"]
        assert summary["high_value"] + summary["medium_value"] + summary["low_value"] == 3

    def test_empty_contacts(self, analyzer):
        """空联系人列表不崩溃。"""
        result = analyzer.analyze([])
        assert result["summary"]["total_contacts"] == 0
        assert result["dormant_alerts"] == []


class TestEdgeCases:
    """边界情况。"""

    def test_no_events_contact(self, analyzer):
        """完全没有事件的联系人。"""
        contact = [{"name": "无名", "birthday": None, "hobbies": [], "key_events": [], "tags": [], "notes": ""}]
        result = analyzer.analyze(contact)
        assert result["summary"]["total_contacts"] == 1

    def test_past_date_handling(self, analyzer):
        """过去的日期正确处理。"""
        contact = [{
            "name": "老友",
            "hobbies": [], "key_events": [
                {"date": "2024年1月", "description": "春节见面"}
            ], "tags": [], "notes": "老朋友"
        }]
        result = analyzer.analyze(contact)
        dormant = result["dormant_alerts"]
        assert len(dormant) == 1
        assert dormant[0]["status"] == "frozen"
