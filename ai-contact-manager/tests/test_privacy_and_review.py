"""
privacy_manager 和 review_queue 的单元测试
"""

import os
import json
import tempfile
import pytest

# ========== Review Queue 测试 ==========

class TestReviewQueue:
    def test_empty_contacts(self):
        from review_queue import ReviewQueue
        rq = ReviewQueue()
        result = rq.scan([])
        assert result == []

    def test_missing_relationship_type(self):
        from review_queue import ReviewQueue
        rq = ReviewQueue()
        contacts = [{"name": "张三", "tags": [], "notes": "上次聊了一下工作"}]
        result = rq.scan(contacts)
        assert len(result) >= 1, "无标签无关系词应触发确认"

    def test_known_relationship_type(self):
        from review_queue import ReviewQueue
        rq = ReviewQueue()
        contacts = [{"name": "张三", "tags": ["程序员"], "notes": "大学同学，程序员"}]
        result = rq.scan(contacts)
        # 有关系标签或关系词，不应触发关系类型确认
        rel_items = [r for r in result if r["category"] == "关系类型"]
        assert len(rel_items) == 0

    def test_missing_birthday(self):
        from review_queue import ReviewQueue
        rq = ReviewQueue()
        contacts = [{"name": "张三", "birthday": None, "tags": ["同学"], "notes": "同学"}]
        result = rq.scan(contacts)
        bday_items = [r for r in result if r["category"] == "生日信息"]
        assert len(bday_items) >= 1

    def test_high_value_blank(self):
        from review_queue import ReviewQueue
        rq = ReviewQueue()
        contacts = [{"name": "李总", "birthday": None, "hobbies": [], "key_events": [], "tags": [], "notes": "某公司CEO，行业峰会认识"}]
        result = rq.scan(contacts)
        high = [r for r in result if r["category"] == "高价值信息补全"]
        assert len(high) >= 1

    def test_icebreaker_blocked(self):
        from review_queue import ReviewQueue
        rq = ReviewQueue()
        contacts = [{"name": "赵总", "tags": [], "notes": "峰会认识，做AI芯片的CTO。想约他聊但不知道从什么话题切入"}]
        result = rq.scan(contacts)
        ice = [r for r in result if r["category"] == "破冰障碍"]
        assert len(ice) >= 1

    def test_each_item_has_options(self):
        from review_queue import ReviewQueue
        rq = ReviewQueue()
        contacts = [{"name": "无名人", "tags": [], "notes": ""}]
        result = rq.scan(contacts)
        for item in result:
            assert len(item.get("options", [])) >= 2
            assert "question" in item
            assert "urgency" in item

    def test_generate_markdown(self):
        from review_queue import ReviewQueue
        rq = ReviewQueue()
        contacts = [{"name": "赵总", "tags": [], "notes": "峰会认识的CTO，不知怎么切入"}]
        rq.scan(contacts)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "REVIEW_QUEUE.md")
            rq.generate_markdown(path)
            assert os.path.exists(path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "赵总" in content
            assert "关系确认队列" in content

    def test_empty_queue_markdown(self):
        from review_queue import ReviewQueue
        rq = ReviewQueue()
        rq.scan([])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "REVIEW_QUEUE.md")
            rq.generate_markdown(path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "0 项" in content


# ========== Privacy Manager 测试 ==========

class TestPrivacyManager:
    """隐私加密测试 —— 仅在 pycryptodome 可用时运行。"""

    @pytest.fixture
    def pm(self):
        try:
            from privacy_manager import PrivacyManager, CRYPTO_AVAILABLE
            if not CRYPTO_AVAILABLE:
                pytest.skip("pycryptodome 未安装")
            return PrivacyManager(tempfile.gettempdir())
        except ImportError:
            pytest.skip("pycryptodome 未安装")

    def test_password_strength(self):
        from privacy_manager import PrivacyManager
        # 弱密码
        weak = PrivacyManager.check_password_strength("123")
        assert weak["level"] == "弱"
        # 强密码
        strong = PrivacyManager.check_password_strength("MyP@ssw0rd!2024")
        assert strong["level"] in ("中", "强")

    def test_encrypt_decrypt(self, pm):
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试文件
            test_file = os.path.join(tmpdir, "test.json")
            with open(test_file, "w", encoding="utf-8") as f:
                json.dump({"data": "sensitive"}, f)

            # 加密
            enc_path = pm.encrypt_file(test_file, "test_password", delete_original=True)
            assert os.path.exists(enc_path)
            assert not os.path.exists(test_file)

            # 解密
            dec_path = pm.decrypt_file(enc_path, "test_password")
            assert os.path.exists(dec_path)
            with open(dec_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert data["data"] == "sensitive"

    def test_wrong_password(self, pm):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.json")
            with open(test_file, "w") as f:
                json.dump({"data": "x"}, f)
            enc_path = pm.encrypt_file(test_file, "correct", delete_original=True)

            with pytest.raises(ValueError, match="密码错误"):
                pm.decrypt_file(enc_path, "wrong")

    def test_share_token(self, pm):
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试数据
            test_file = os.path.join(tmpdir, "test.json")
            data = {"contacts": [{"name": "张三", "birthday": "01-01"}]}
            with open(test_file, "w", encoding="utf-8") as f:
                json.dump(data, f)

            # 加密
            enc_path = pm.encrypt_file(test_file, "mypassword", delete_original=True)

            # 生成分享令牌
            share = pm.generate_share_token(enc_path, "mypassword", "张三")
            assert "token" in share
            assert "temp_password" in share
            assert share["contact"] == "张三"

    def test_access_log(self, pm):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.json")
            with open(test_file, "w") as f:
                json.dump({"data": "x"}, f)
            enc_path = pm.encrypt_file(test_file, "pw")
            pm.decrypt_file(enc_path, "pw")

            log = pm.get_access_log()
            assert len(log) >= 2
