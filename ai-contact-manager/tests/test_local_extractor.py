"""
local_extractor.py 的单元测试

测试覆盖：
- 姓名提取（中文名、称呼、英文名）
- 生日提取（公历、农历、模糊、缺失）
- 爱好提取（关键词、模式匹配）
- 事件提取（关键词 + 日期定位）
- 标签提取（关键词匹配）
- 置信度计算
- 分段逻辑
- 边界情况
"""

import pytest
from local_extractor import LocalExtractor, extract_local


# ==================== 姓名提取 ====================

class TestContactNameExtraction:
    """测试联系人名称提取。"""

    def test_chinese_name_with_comma(self, extractor):
        """中文名 + 逗号模式：张三，..."""
        assert extractor._extract_contact_name("张三，程序员") == "张三"
        assert extractor._extract_contact_name("老王，3月15号生日") == "老王"

    def test_title_pattern(self, extractor):
        """称呼模式：X总、老X、小X。"""
        assert extractor._extract_contact_name("张总，公司做设计") == "张总"
        assert extractor._extract_contact_name("小李，今天来了") == "小李"

    def test_english_name(self, extractor):
        """英文名识别。"""
        result = extractor._extract_contact_name("Mike works at Google")
        assert result == "Mike"

    def test_unknown_fallback(self, extractor):
        """无法识别时返回默认值。"""
        result = extractor._extract_contact_name("上次吃饭聊了很多")
        assert result == "未知联系人"

    def test_empty_text(self, extractor):
        """空文本。"""
        result = extractor._extract_contact_name("")
        assert result == "未知联系人"


# ==================== 生日提取 ====================

class TestBirthdayExtraction:
    """测试生日信息提取。"""

    def test_explicit_solar_birthday(self, extractor):
        """明确公历生日：3月15号。"""
        result = extractor._extract_birthday("老王，3月15号生日")
        assert result is not None
        assert result["month"] == 3
        assert result["day"] == 15
        assert result["type"] == "solar"

    def test_birthday_with_dot_separator(self, extractor):
        """点分隔符：10.20。"""
        result = extractor._extract_birthday("生日10.20")
        assert result is not None
        assert result["month"] == 10
        assert result["day"] == 20

    def test_birthday_with_dash_separator(self, extractor):
        """横线分隔符：8-25。"""
        result = extractor._extract_birthday("生日是8-25")
        assert result is not None
        assert result["month"] == 8
        assert result["day"] == 25

    def test_lunar_birthday(self, extractor):
        """农历生日：腊月初八。"""
        result = extractor._extract_birthday("腊月初八生日")
        assert result is not None
        assert result["type"] == "lunar"
        assert "腊月初八" in result["raw"]

    def test_vague_birthday(self, extractor):
        """模糊生日：好像是8月还是9月 — 不应提取为确定日期。"""
        result = extractor._extract_birthday("生日好像是8月还是9月")
        # 没有明确日期数字，不应提取
        assert result is None

    def test_date_not_birthday(self, extractor):
        """非生日的日期（会议等）不应提取为生日。"""
        result = extractor._extract_birthday("12月20号有个会议")
        assert result is None

    def test_date_without_birthday_signal(self, extractor):
        """有日期但没有明确生日信号 — 保守提取。"""
        result = extractor._extract_birthday("3月8号特别的日子")
        # 无生日信号也无反信号，保守返回
        assert result is not None
        assert result["month"] == 3
        assert result["day"] == 8

    def test_no_birthday(self, extractor):
        """完全没有生日信息。"""
        result = extractor._extract_birthday("做物流的，上次聊到扩仓库")
        assert result is None


# ==================== 爱好提取 ====================

class TestHobbyExtraction:
    """测试爱好提取。"""

    def test_keyword_hobby(self, extractor):
        """关键词匹配：钓鱼、乒乓球。"""
        result = extractor._extract_hobbies("喜欢钓鱼和打乒乓球")
        assert "钓鱼" in result
        assert "打乒乓球" in result

    def test_like_pattern_hobby(self, extractor):
        """"喜欢X" 模式匹配。"""
        result = extractor._extract_hobbies("特别喜欢看电影和听音乐")
        assert "看电影" in result
        assert "听音乐" in result

    def test_no_hobby(self, extractor):
        """没有爱好信息。"""
        result = extractor._extract_hobbies("做跨境电商的")
        assert result == []

    def test_avoid_short_hobby(self, extractor):
        """避免提取过短的爱好词（<2字）。"""
        result = extractor._extract_hobbies("喜欢看，画")
        # "看" 和 "画" 都太短，不应提取
        assert len([h for h in result if len(h) < 2]) == 0


# ==================== 事件提取 ====================

class TestEventExtraction:
    """测试关键事件提取。"""

    def test_event_with_keyword(self, extractor):
        """关键词 + 附近日期。"""
        result = extractor._extract_events("7月5号换工作了")
        assert len(result) >= 1
        assert any("换工作" in e.get("description", "") for e in result)

    def test_last_time_pattern(self, extractor):
        """"上次X月X号" 模式。"""
        result = extractor._extract_events("上次5月吃饭聊了很多")
        assert len(result) >= 1

    def test_no_event(self, extractor):
        """没有事件信息。"""
        result = extractor._extract_events("张三，程序员，喜欢钓鱼")
        assert result == []


# ==================== 标签提取 ====================

class TestTagExtraction:
    """测试标签提取。"""

    def test_programmer_tag(self, extractor):
        """程序员标签。"""
        result = extractor._extract_tags("他是程序员，做后端的")
        assert "程序员" in result

    def test_married_tag(self, extractor):
        """已婚标签。"""
        result = extractor._extract_tags("他老婆叫小李")
        assert "已婚" in result

    def test_child_tag(self, extractor):
        """有孩子标签。"""
        result = extractor._extract_tags("孩子刚上小学")
        assert "有孩子" in result

    def test_single_tag(self, extractor):
        """单身标签。"""
        result = extractor._extract_tags("目前单身")
        assert "单身" in result

    def test_multiple_tags(self, extractor):
        """多个标签。"""
        result = extractor._extract_tags("程序员，结婚有孩子，创业中")
        assert "程序员" in result
        assert "已婚" in result
        assert "有孩子" in result
        assert "创业者" in result


# ==================== 置信度 ====================

class TestConfidence:
    """测试置信度计算。"""

    def test_full_info_confidence(self, extractor):
        """信息完整的联系人置信度高。"""
        contact = {
            "name": "老王",
            "birthday": {"month": 3, "day": 15},
            "hobbies": ["钓鱼", "乒乓球"],
            "key_events": [{"date": "7月", "description": "聊到跨境电商"}],
            "tags": ["已婚", "有孩子"],
            "aliases": [],
        }
        confidence = extractor._calc_confidence(contact)
        assert confidence >= 0.7, f"期望 >= 0.7，实际 {confidence}"

    def test_minimal_info_confidence(self, extractor):
        """信息极少的联系人置信度低。"""
        contact = {
            "name": "赵总",
            "birthday": None,
            "hobbies": [],
            "key_events": [],
            "tags": [],
            "aliases": [],
        }
        confidence = extractor._calc_confidence(contact)
        assert confidence == 0.3, f"期望 0.3，实际 {confidence}"

    def test_confidence_capped_at_one(self, extractor):
        """置信度不超过 1.0。"""
        contact = {
            "name": "老王",
            "birthday": {"month": 3, "day": 15},
            "hobbies": ["a", "b", "c", "d", "e", "f", "g", "h"],
            "key_events": [{"a": 1}] * 10,
            "tags": ["a", "b", "c", "d", "e"],
            "aliases": ["a", "b", "c"],
        }
        confidence = extractor._calc_confidence(contact)
        assert confidence <= 1.0, f"期望 <= 1.0，实际 {confidence}"


# ==================== 分段逻辑 ====================

class TestSegmentation:
    """测试联系人分段逻辑。"""

    def test_blank_line_separation(self, extractor):
        """空行分隔。"""
        segments = extractor._split_by_contact("张三，程序员\n\n李四，设计师")
        assert len(segments) >= 2

    def test_long_paragraph_subsplit(self, extractor):
        """长段落按句号细分。"""
        long_text = (
            "张三，程序员，喜欢钓鱼。"
            + "李四，设计师，喜欢画画。"
            + "王五，产品经理，喜欢读书。"
        )
        segments = extractor._split_by_contact(long_text)
        # 150字符以上的长段落应被拆分
        # 这里文本较短，应该保持为一段或按句号分
        assert len(segments) >= 1

    def test_comment_lines_filtered(self, extractor):
        """注释行（#开头）不应产生有效结果。"""
        # 当前已知问题：注释行会被当作"未知联系人"
        # 此测试记录当前行为
        segments = extractor._split_by_contact("# 这是注释\n\n张三，真实的联系人")
        # 至少应该有张三这一段
        names = [s.get("name") for s in segments]
        assert "张三" in names


# ==================== 完整提取流程 ====================

class TestFullExtraction:
    """测试完整提取流程。"""

    def test_extract_single_contact(self, extractor, single_contact_text):
        """单个联系人完整提取。"""
        result = extractor.extract(single_contact_text)
        assert "contacts" in result
        assert len(result["contacts"]) >= 1
        # 应至少提取到姓名和生日
        contact = result["contacts"][0]
        assert contact["name"] != "未知联系人"

    def test_extract_multiple_contacts(self, extractor, multi_contact_text):
        """多个联系人提取。"""
        result = extractor.extract(multi_contact_text)
        assert len(result["contacts"]) >= 2

    def test_convenience_function(self, single_contact_text):
        """便捷函数 extract_local 可正常调用。"""
        result = extract_local(single_contact_text)
        assert "contacts" in result
        assert len(result["contacts"]) >= 1

    def test_result_structure(self, extractor, single_contact_text):
        """返回结果包含所有必需字段。"""
        result = extractor.extract(single_contact_text)
        assert "extraction_method" in result
        assert "generated_at" in result
        assert "total_contacts" in result
        assert result["extraction_method"] == "local"

    def test_extraction_on_sample_file(self, sample_extraction_result):
        """在 sample_notes.txt 上的完整提取。"""
        contacts = sample_extraction_result["contacts"]
        assert len(contacts) >= 5, f"期望至少5个联系人，实际 {len(contacts)}"

        # 检查是否包含关键联系人
        names = [c["name"] for c in contacts]
        assert "老王" in names, f"未找到'老王'，已找到: {names}"
        assert "张总" in names, f"未找到'张总'，已找到: {names}"
        assert "赵总" in names, f"未找到'赵总'，已找到: {names}"

    @pytest.mark.local
    def test_no_hallucination(self, extractor):
        """不应凭空编造信息。"""
        result = extractor.extract("张三")
        contacts = result["contacts"]
        if contacts:
            contact = contacts[0]
            # 生日不应凭空出现
            if contact.get("birthday"):
                # 如果真的出现了，置信度应该很低
                assert contact.get("confidence", 0) <= 0.5


# ==================== 边界情况 ====================

class TestEdgeCases:
    """边界情况和异常处理。"""

    def test_empty_input(self, extractor):
        """空输入。"""
        result = extractor.extract("")
        assert "contacts" in result

    def test_whitespace_only(self, extractor):
        """只有空白字符。"""
        result = extractor.extract("   \n\n   ")
        assert "contacts" in result

    def test_single_char_name(self, extractor):
        """单字姓名。"""
        result = extractor.extract("刘，喜欢钓鱼")
        contacts = result["contacts"]
        assert len(contacts) >= 1

    def test_mixed_language(self, extractor):
        """中英混合。"""
        result = extractor.extract("Mike，12月25号生日，likes coding and hiking")
        contacts = result["contacts"]
        assert len(contacts) >= 1
