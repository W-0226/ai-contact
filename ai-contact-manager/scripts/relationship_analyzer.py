"""
关系价值评估与断联分析模块

功能：
1. 关系价值评分 — 四维度综合评估（信息完整度/亲密度/联系质量/潜在价值）
2. 断联状态分级 — 五级分类（活跃/变冷/冻结/僵尸）
3. 原因诊断 — 自动判断断联可能原因
4. 后续方案 — 针对不同原因给出可执行的行动建议

无需外部依赖，纯逻辑计算。
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import re
import logging

logger = logging.getLogger(__name__)


class RelationshipAnalyzer:
    """关系价值评估与断联分析器。"""

    # ========== 断联阈值配置 ==========

    THRESHOLD_ACTIVE = 30       # ≤30天 = 活跃
    THRESHOLD_COOLING = 90      # ≤90天 = 变冷
    THRESHOLD_COLD = 365        # ≤365天 = 冻结（超过即为僵尸）

    # ========== 关系类型权重 ==========

    RELATIONSHIP_WEIGHTS = {
        # 亲密关系
        "家人": 25, "亲戚": 22, "发小": 25, "闺蜜": 22, "哥们": 20,
        # 强关系
        "大学同学": 18, "高中同学": 16, "室友": 18, "同事": 15,
        "前同事": 12, "导师": 20, "老师": 18, "学生": 12,
        # 中等关系
        "朋友": 15, "球友": 12, "书友": 10, "健身": 8,
        "邻居": 10, "老乡": 8,
        # 弱关系
        "合作伙伴": 12, "客户": 10, "供应商": 8, "介绍": 5,
        "峰会": 3, "展会": 3, "活动": 3, "认识": 2,
    }

    # ========== 价值信号关键词 ==========

    HIGH_VALUE_SIGNALS = [
        # 商业价值
        "创业", "CEO", "CTO", "创始人", "合伙人", "总监", "VP", "副总",
        "老板", "融资", "IPO", "上市", "投资人", "项目", "合作",
        # 行业资源
        "字节", "腾讯", "阿里", "华为", "百度", "大厂",
        # 知识价值
        "教授", "博士", "专家", "导师", "咨询",
    ]

    MEDIUM_VALUE_SIGNALS = [
        "经理", "主管", "负责人", "团队", "业务",
    ]

    def __init__(self, today: Optional[datetime] = None):
        """
        初始化分析器。

        Args:
            today: 基准日期，默认当天
        """
        self.today = today
        if today is None:
            self.today = datetime.now().date()
        elif isinstance(today, datetime):
            self.today = today.date()
        else:
            self.today = today  # already a date object

    # ========== 公开接口 ==========

    def analyze(self, contacts: List[Dict]) -> Dict:
        """
        对联系人列表进行完整的关系分析。

        Args:
            contacts: 提取引擎输出的 contacts 列表

        Returns:
            {
                "scored_contacts": [...],   # 每个联系人附上评分
                "value_ranking": [...],      # 按价值降序排列
                "dormant_alerts": [...],     # 断联预警列表
                "summary": {...},            # 汇总统计
            }
        """
        # Step 1: 逐个评分
        scored = []
        for contact in contacts:
            score_detail = self._score_contact(contact)
            contact_copy = dict(contact)
            contact_copy["relationship_score"] = score_detail
            scored.append(contact_copy)

        # Step 2: 价值排名
        ranking = sorted(scored, key=lambda c: c["relationship_score"]["total"], reverse=True)

        # Step 3: 断联分析
        dormant = self._analyze_dormant(scored)

        # Step 4: 汇总
        summary = {
            "total_contacts": len(scored),
            "high_value": len([c for c in scored if c["relationship_score"]["total"] >= 70]),
            "medium_value": len([c for c in scored if 40 <= c["relationship_score"]["total"] < 70]),
            "low_value": len([c for c in scored if c["relationship_score"]["total"] < 40]),
            "dormant_count": len(dormant),
            "zombie_count": len([d for d in dormant if d["status"] == "zombie"]),
            "need_action_count": len([d for d in dormant if d["status"] in ("frozen", "zombie")]),
        }

        return {
            "scored_contacts": scored,
            "value_ranking": ranking,
            "dormant_alerts": dormant,
            "summary": summary,
        }

    # ========== 价值评分 ==========

    def _score_contact(self, contact: Dict) -> Dict:
        """
        四维度关系价值评分。

        Returns:
            {
                "total": int,           # 总分 0-100
                "info_completeness": int,  # 信息完整度 0-25
                "intimacy": int,           # 关系亲密度 0-25
                "contact_quality": int,    # 联系质量 0-25
                "potential_value": int,    # 潜在价值 0-25
                "level": str,              # high/medium/low
                "highlights": [str],       # 得分亮点
                "weaknesses": [str],       # 扣分项
            }
        """
        info = self._score_info_completeness(contact)
        intimacy = self._score_intimacy(contact)
        quality = self._score_contact_quality(contact)
        potential = self._score_potential(contact)

        total = info + intimacy + quality + potential

        # 分级
        if total >= 70:
            level = "high"
        elif total >= 40:
            level = "medium"
        else:
            level = "low"

        # 亮点和弱项
        highlights = []
        weaknesses = []
        if info >= 18:
            highlights.append("信息完整，容易维护")
        elif info < 10:
            weaknesses.append("信息严重不足，建议花时间了解")
        if intimacy >= 18:
            highlights.append("关系密切")
        if quality >= 18:
            highlights.append("近期联系活跃")
        elif quality < 8:
            weaknesses.append("长期未联系，关系降温风险")
        if potential >= 18:
            highlights.append("潜在价值高，值得重点维护")

        return {
            "total": total,
            "info_completeness": info,
            "intimacy": intimacy,
            "contact_quality": quality,
            "potential_value": potential,
            "level": level,
            "highlights": highlights,
            "weaknesses": weaknesses,
        }

    def _score_info_completeness(self, contact: Dict) -> int:
        """信息完整度评分（0-25）。"""
        score = 0
        if contact.get("birthday"):
            score += 10  # 生日最重要
        if contact.get("hobbies"):
            score += min(5, len(contact["hobbies"]) * 2)
        if contact.get("key_events"):
            score += min(5, len(contact["key_events"]) * 2)
        if contact.get("tags"):
            score += min(5, len(contact["tags"]) * 2)
        return min(score, 25)

    def _score_intimacy(self, contact: Dict) -> int:
        """关系亲密度评分（0-25）。"""
        score = 10  # 基础分

        notes = contact.get("notes", "")
        tags = contact.get("tags", [])

        # 从备注中匹配关系类型
        for rel_type, weight in self.RELATIONSHIP_WEIGHTS.items():
            if rel_type in notes:
                score = max(score, weight)
                break

        # 标签加成
        intimate_tags = {"家人", "亲戚", "已婚", "有孩子"}
        tag_bonus = sum(3 for t in tags if t in intimate_tags)
        score += tag_bonus

        # 有共同经历加成
        shared_signals = ["以前", "一起", "共同", "合作过", "合租", "室友"]
        if any(s in notes for s in shared_signals):
            score += 3

        return min(score, 25)

    def _score_contact_quality(self, contact: Dict) -> int:
        """联系质量评分（0-25），基于最近联系时间和事件深度。"""
        score = 10  # 基础分

        events = contact.get("key_events", [])
        notes = contact.get("notes", "")

        # 有事件 = 有互动 = 质量加分
        score += min(8, len(events) * 3)

        # 最近联系时间越近分越高
        days_since = self._estimate_days_since_latest(events, notes)
        if days_since is not None:
            if days_since <= self.THRESHOLD_ACTIVE:
                score += 7
            elif days_since <= self.THRESHOLD_COOLING:
                score += 4
            elif days_since <= self.THRESHOLD_COLD:
                score += 1
            # > 365天不加分

        # "从来/从未/没联系" = 扣分
        if any(w in notes for w in ["没联系", "从未", "从来不", "没聊过"]):
            score -= 5

        return max(0, min(score, 25))

    def _score_potential(self, contact: Dict) -> int:
        """潜在价值评分（0-25）。"""
        score = 5  # 基础分（每个人都有基本社交价值）

        notes = contact.get("notes", "")

        # 高价值信号
        high_count = sum(1 for s in self.HIGH_VALUE_SIGNALS if s in notes)
        score += min(15, high_count * 4)

        # 中价值信号
        medium_count = sum(1 for s in self.MEDIUM_VALUE_SIGNALS if s in notes)
        score += min(5, medium_count * 2)

        return min(score, 25)

    # ========== 断联分析 ==========

    def _analyze_dormant(self, scored_contacts: List[Dict]) -> List[Dict]:
        """
        分析所有联系人的断联状态。

        Returns:
            断联预警列表（仅包含非活跃联系人，按严重程度排序）
        """
        alerts = []

        for contact in scored_contacts:
            days = self._get_days_since_last_contact(contact)

            if days is None:
                # 从未联系
                status = "zombie"
                days_display = None
            elif days <= self.THRESHOLD_ACTIVE:
                continue  # 活跃联系人，不预警
            elif days <= self.THRESHOLD_COOLING:
                status = "cooling"
                days_display = days
            elif days <= self.THRESHOLD_COLD:
                status = "cold"
                days_display = days
            else:
                status = "frozen"
                days_display = days

            # 诊断原因
            reasons = self._diagnose_reasons(contact, status, days_display)

            # 生成方案
            action_plan = self._generate_action_plan(contact, status, reasons)

            score = contact.get("relationship_score", {})

            alerts.append({
                "name": contact["name"],
                "status": status,
                "status_label": {
                    "cooling": "开始变冷",
                    "cold": "已冻结",
                    "frozen": "深度冻结",
                    "zombie": "僵尸人脉（从未激活）",
                }.get(status, status),
                "days_since_contact": days_display,
                "value_level": score.get("level", "low"),
                "reasons": reasons,
                "action_plan": action_plan,
                "should_let_go": self._should_let_go(contact, status, score),
            })

        # 排序：僵尸 > 冻结 > 变冷，高价值优先
        status_order = {"zombie": 0, "frozen": 1, "cold": 2, "cooling": 3}
        alerts.sort(key=lambda a: (
            status_order.get(a["status"], 99),
            -(a.get("value_level") == "high"),
        ))

        return alerts

    def _get_days_since_last_contact(self, contact: Dict) -> Optional[int]:
        """获取距上次联系的天数。"""
        events = contact.get("key_events", [])
        notes = contact.get("notes", "")

        # "从未/没联系过"
        if any(w in notes for w in ["没联系", "从未", "从来不", "没聊过", "一直没联系"]):
            return None

        return self._estimate_days_since_latest(events, notes)

    def _estimate_days_since_latest(self, events: List[Dict], notes: str = "") -> Optional[int]:
        """从事件列表和备注中估算最近联系距今天数。"""
        best_days = None

        # 从事件日期估算
        for event in events:
            date_str = event.get("date", "")
            if not date_str:
                continue
            days = self._parse_date_to_days(date_str)
            if days is not None and (best_days is None or days < best_days):
                best_days = days

        # 从备注中的时间表达估算
        time_patterns = [
            (r"(\d+)天前", lambda m: int(m.group(1))),
            (r"(\d+)周前", lambda m: int(m.group(1)) * 7),
            (r"上个?月", lambda m: 30),
            (r"前[两三]天", lambda m: 3),
            (r"前[一两]周", lambda m: 10),
        ]
        for pattern, calc in time_patterns:
            match = re.search(pattern, notes)
            if match:
                days = calc(match)
                if best_days is None or days < best_days:
                    best_days = days

        return best_days

    def _parse_date_to_days(self, date_str: str) -> Optional[int]:
        """解析日期字符串为距今天数。"""
        # 带年份
        match = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})?", date_str)
        if match:
            year, month = int(match.group(1)), int(match.group(2))
            day = int(match.group(3)) if match.group(3) else 15
            try:
                event_date = datetime(year, month, day).date()
                return (self.today - event_date).days
            except ValueError:
                return None

        # X月X号
        match = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})", date_str)
        if match:
            month, day = int(match.group(1)), int(match.group(2))
            try:
                event_date = datetime(self.today.year, month, day).date()
                if event_date > self.today:
                    event_date = datetime(self.today.year - 1, month, day).date()
                return (self.today - event_date).days
            except ValueError:
                pass

        # 仅X月（取月中）
        match = re.search(r"(\d{1,2})\s*月", date_str)
        if match:
            month = int(match.group(1))
            try:
                event_date = datetime(self.today.year, month, 15).date()
                if event_date > self.today:
                    event_date = datetime(self.today.year - 1, month, 15).date()
                return (self.today - event_date).days
            except ValueError:
                pass

        return None

    # ========== 原因诊断 ==========

    def _diagnose_reasons(self, contact: Dict, status: str, days: Optional[int]) -> List[Dict]:
        """
        诊断断联的可能原因。

        Returns:
            [{ "reason": str, "confidence": float, "evidence": str }]
        """
        reasons = []
        notes = contact.get("notes", "")
        score = contact.get("relationship_score", {})
        info_score = score.get("info_completeness", 0)

        # 1. 纯僵尸：从未联系 + 信息极少
        if status == "zombie" and info_score < 10:
            reasons.append({
                "reason": "纯陌生人 — 加了微信/名片但从未建立联系",
                "confidence": 0.9,
                "evidence": "无聊天记录、信息几乎空白",
            })

        # 2. 信息黑洞
        if info_score < 10:
            reasons.append({
                "reason": "信息黑洞 — 对TA了解太少，不知从何聊起",
                "confidence": 0.8,
                "evidence": f"生日/爱好/近期事件均缺失或极少",
            })

        # 3. 场景消失
        scene_signals = {
            "前同事": "已不在同一家公司，缺乏日常交集",
            "室友": "已不再合租，共同生活场景消失",
            "合租": "已不再合租，共同生活场景消失",
            "以前": "过往的共同场景已结束",
            "之前": "过往的共同场景已结束",
            "实习": "实习期结束，不再有工作交集",
            "培训": "培训/课程结束，学习场景消失",
        }
        for signal, desc in scene_signals.items():
            if signal in notes:
                reasons.append({
                    "reason": f"场景消失 — {desc}",
                    "confidence": 0.7,
                    "evidence": notes[:100],
                })
                break

        # 4. 自然疏远
        if days and days > 180:
            has_common = bool(contact.get("hobbies"))
            if not has_common:
                reasons.append({
                    "reason": "自然疏远 — 无共同兴趣/话题，联系缺乏自然切入点",
                    "confidence": 0.6,
                    "evidence": f"已{int(days/30)}个月未联系，且无共同爱好",
                })

        # 5. 单向关系（信息少但对方有价值 — 你够不着）
        if score.get("potential_value", 0) >= 15 and info_score < 15:
            reasons.append({
                "reason": "单向仰视 — 对方价值高但你对TA了解不够，缺乏平等对话基础",
                "confidence": 0.65,
                "evidence": "对方潜在价值高，但你掌握的信息不足以发起自然对话",
            })

        # 确保至少有一个原因
        if not reasons:
            reasons.append({
                "reason": "联系节奏放缓 — 可能是双方都忙，缺乏主动联系契机",
                "confidence": 0.5,
                "evidence": f"距上次联系约{int(days/30) if days else '未知'}个月",
            })

        return reasons

    # ========== 方案生成 ==========

    def _generate_action_plan(self, contact: Dict, status: str, reasons: List[Dict]) -> Dict:
        """
        根据断联状态和原因生成后续行动方案。

        Returns:
            {
                "urgency": str,         # 紧急程度
                "recommended_action": str,  # 推荐动作
                "icebreaker": str,      # 破冰话术建议
                "timing": str,          # 建议时机
                "fallback": str,        # 备选方案
            }
        """
        name = contact.get("name", "TA")
        hobbies = contact.get("hobbies", [])
        events = contact.get("key_events", [])
        birthday = contact.get("birthday")
        score = contact.get("relationship_score", {})

        # 默认方案
        plan = {
            "urgency": "low",
            "recommended_action": "",
            "icebreaker": "",
            "timing": "近期任意时间",
            "fallback": "如无回应，三个月后再尝试一次",
        }

        # ==== 按状态和原因定制 ====

        if status == "zombie":
            plan["urgency"] = "medium" if score.get("total", 0) >= 40 else "low"

            if score.get("potential_value", 0) >= 15:
                plan["recommended_action"] = "高价值僵尸人脉，建议以行业动态为切入点激活"
                plan["icebreaker"] = f"「{name}你好，最近看到[行业新闻]，想起上次在[场合]聊过，想请教一下…」"
                plan["timing"] = "关注TA所在行业有重大新闻时"
            else:
                plan["recommended_action"] = "可选择性激活或放手"
                plan["icebreaker"] = f"「{name}你好，之前在[场合]加的好友，最近怎么样？」"
                plan["fallback"] = "如无回应，可以放手"

        elif status == "frozen":
            plan["urgency"] = "high" if score.get("total", 0) >= 50 else "medium"
            plan["recommended_action"] = "深度冻结，需要强理由重启联系"

            # 有生日 = 天然时机
            if birthday:
                month, day = birthday.get("month"), birthday.get("day")
                plan["icebreaker"] = f"「{name}好久不见！记得你生日快到了，提前祝你生日快乐🎂最近怎么样？」"
                plan["timing"] = f"生日前后（{month}月{day}日）"
            elif events:
                latest = events[-1]
                plan["icebreaker"] = f"「{name}好久没联系了！突然想起上次聊到{latest.get('description','')}，后来怎么样啦？」"
                plan["timing"] = "近期"
            elif hobbies:
                plan["icebreaker"] = f"「{name}好久不见！最近还在{hobbies[0]}吗？我刚入坑想请教一下」"
                plan["timing"] = "周末或节假日"

            plan["fallback"] = "如三次尝试无果，降级为年度问候联系人"

        elif status == "cold":
            plan["urgency"] = "medium"
            plan["recommended_action"] = "已数月未联系，适合用节日或共同话题重启"

            if hobbies:
                plan["icebreaker"] = f"「{name}，最近看到一个{hobbies[0]}的活动/新闻，突然想到你，最近怎么样？」"
            elif events:
                latest = events[-1]
                plan["icebreaker"] = f"「{name}，最近忙吗？突然想起上次聊到{latest.get('description','')}，想跟你update一下」"
            else:
                plan["icebreaker"] = f"「{name}好久不见，最近一切都顺利吗？」"
            plan["timing"] = "近期节假日或周末"

        else:  # cooling
            plan["urgency"] = "low"
            plan["recommended_action"] = "关系开始降温，趁还有温度尽早联系一次"
            plan["icebreaker"] = f"「{name}最近怎么样？好久没聊了～」"
            plan["timing"] = "本周或下周"

        return plan

    # ========== 放手判断 ==========

    def _should_let_go(self, contact: Dict, status: str, score: Dict) -> bool:
        """判断是否建议放手这个关系。"""
        # 僵尸 + 低价值 = 可以放手
        if status == "zombie" and score.get("total", 0) < 25:
            return True
        # 深度冻结 + 极低信息 + 低价值
        if status == "frozen" and score.get("info_completeness", 0) < 8 and score.get("total", 0) < 20:
            return True
        return False
