"""
测试夹具和共用工具 — 为所有测试模块提供 fixture。
"""

import os
import sys
import pytest

# 将 scripts 目录加入 Python 路径
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from local_extractor import LocalExtractor
from generate_reminders import ReminderGenerator, generate_all


# ========== 共用 fixture ==========

@pytest.fixture
def extractor():
    """默认的本地规则提取器实例。"""
    return LocalExtractor()


@pytest.fixture
def sample_notes_path():
    """sample_notes.txt 的路径。"""
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data", "sample_notes.txt"
    )


@pytest.fixture
def sample_text():
    """sample_notes.txt 的完整文本内容。"""
    path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data", "sample_notes.txt"
    )
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def sample_extraction_result(extractor, sample_text):
    """对 sample_notes.txt 的完整提取结果。"""
    return extractor.extract(sample_text)


# ========== 测试用微型数据 ==========

@pytest.fixture
def single_contact_text():
    """单个联系人的简单备注。"""
    return "老张，2月14号生日，喜欢钓鱼和打游戏。上次3月聊到他在创业做跨境电商。"


@pytest.fixture
def multi_contact_text():
    """多个联系人的备注。"""
    return (
        "小明，8月8号生日，喜欢看电影。\n\n"
        "小红，12月25号生日，喜欢做烘焙。"
    )


@pytest.fixture
def vague_birthday_text():
    """生日模糊的备注。"""
    return "李总，生日好像是5月还是6月，喜欢喝茶。"


@pytest.fixture
def lunar_birthday_text():
    """农历生日的备注。"""
    return "阿姨，腊月初八生日，喜欢跳广场舞。"


@pytest.fixture
def no_birthday_text():
    """没有生日信息的备注。"""
    return "王经理，公司是做物流的，上次聊到要扩仓库。"


@pytest.fixture
def minimal_contacts_data():
    """最小化的联系人数据，用于测试提醒生成器。"""
    return {
        "contacts": [
            {
                "name": "张三",
                "birthday": {"month": 7, "day": 20, "type": "solar", "raw": "7月20号"},
                "hobbies": ["跑步"],
                "key_events": [
                    {"date": "2026年5月", "description": "聊到换工作"}
                ],
                "tags": ["程序员"],
                "confidence": 0.9,
                "source": "local",
            },
            {
                "name": "李四",
                "birthday": {"month": 12, "day": 25, "type": "solar", "raw": "12月25号"},
                "hobbies": ["摄影"],
                "key_events": [],
                "tags": ["设计师"],
                "confidence": 0.8,
                "source": "local",
            },
        ]
    }
