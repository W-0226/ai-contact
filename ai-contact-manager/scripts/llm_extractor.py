# -*- coding: utf-8 -*-
"""
LLM 增强提取引擎 — 当本地规则引擎置信度不足时，
调用 LLM API 对文本进行语义级别的信息提取。

支持的提供商：OpenAI / DeepSeek / 兼容 OpenAI 格式的自定义 API。
"""

import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class LLMExtractor:
    """基于 LLM API 的语义信息提取器。"""

    # 默认系统提示词
    DEFAULT_SYSTEM_PROMPT = """你是一个人脉关系信息提取助手。
你的任务是从非结构化的聊天备注文本中提取结构化的联系人信息。

对于每个联系人，请提取以下信息（如果文本中提到）：
1. name: 联系人名称
2. birthday: 生日，格式为 {"month": 数字, "day": 数字, "type": "solar"|"lunar"|"unknown"}
3. hobbies: 爱好列表
4. key_events: 关键事件列表，每项为 {"date": "日期描述", "description": "事件描述"}
5. tags: 标签列表（如"创业者"、"已婚"、"学生"等）
6. relationship: 与用户的关系（如"大学同学"、"前同事"、"客户"）
7. notes: 其他值得记录的备注信息

请以 JSON 数组格式返回，每个元素是一个联系人对象。
只返回 JSON，不要包含其他文字。"""

    def __init__(
        self,
        provider: str = "deepseek",
        api_key: str = None,
        model: str = None,
        base_url: str = None,
    ):
        """
        初始化 LLM 提取器。

        Args:
            provider: "openai" | "deepseek" | "custom"
            api_key: API 密钥
            model: 模型名称
            base_url: 自定义 API 端点（对 custom provider 有效）
        """
        self.provider = provider
        self.api_key = api_key
        self.model = model or self._default_model(provider)
        self.base_url = base_url or self._default_base_url(provider)

    def _default_model(self, provider: str) -> str:
        defaults = {
            "openai": "gpt-4o",
            "deepseek": "deepseek-chat",
            "custom": "default",
        }
        return defaults.get(provider, "deepseek-chat")

    def _default_base_url(self, provider: str) -> str:
        defaults = {
            "openai": "https://api.openai.com/v1",
            "deepseek": "https://api.deepseek.com/v1",
            "custom": "",
        }
        return defaults.get(provider, "")

    def extract(self, text: str, low_confidence_items: List[Dict] = None) -> Dict:
        """
        使用 LLM 提取联系人信息。

        Args:
            text: 原始聊装备注文本。
            low_confidence_items: 本地引擎返回的低置信度条目（可选），
                                  帮助 LLM 聚焦需要增强的部分。

        Returns:
            与 LocalExtractor.extract() 同格式的结果字典。
        """
        if not self.api_key:
            raise ValueError("LLM 模式需要提供 api_key。请在 llm_config 中配置。")

        # 构建用户提示
        user_prompt = self._build_user_prompt(text, low_confidence_items)

        # 调用 LLM API
        try:
            raw_response = self._call_api(user_prompt)
            contacts = self._parse_response(raw_response)

            # 标记数据来源
            for contact in contacts:
                contact["source"] = "llm"

            return {
                "contacts": contacts,
                "extraction_method": f"llm_{self.provider}",
                "model": self.model,
                "total_contacts": len(contacts),
            }

        except Exception as e:
            logger.error(f"LLM 提取失败: {e}")
            raise

    def _build_user_prompt(
        self, text: str, low_confidence_items: List[Dict] = None
    ) -> str:
        """构建发送给 LLM 的用户提示词。"""
        prompt = f"请从以下聊天备注中提取联系人信息：\n\n```\n{text}\n```"

        if low_confidence_items:
            prompt += "\n\n以下条目本地规则引擎已提取但置信度较低，请重点确认和补充：\n"
            for item in low_confidence_items:
                prompt += f"- {json.dumps(item, ensure_ascii=False)}\n"

        return prompt

    def _call_api(self, user_prompt: str) -> str:
        """调用 OpenAI 兼容 API。"""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "LLM 模式需要 openai 包。请运行: pip install openai"
            )

        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        client = OpenAI(**client_kwargs)

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.DEFAULT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,  # 低温度，追求一致性
            response_format={"type": "json_object"} if "gpt-4" in self.model or "gpt-3.5" in self.model else None,
        )

        return response.choices[0].message.content

    def _parse_response(self, raw_response: str) -> List[Dict]:
        """解析 LLM 返回的 JSON 字符串。"""
        # 尝试直接解析
        try:
            data = json.loads(raw_response)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("contacts", data.get("data", [data]))
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 代码块
        import re
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_response)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        logger.warning(f"无法解析 LLM 响应为 JSON: {raw_response[:200]}...")
        return []


# 便捷函数
def extract_with_llm(
    text: str,
    provider: str = "deepseek",
    api_key: str = None,
    model: str = None,
    base_url: str = None,
    low_confidence_items: List[Dict] = None,
) -> Dict:
    """LLM 提取的便捷入口。"""
    extractor = LLMExtractor(
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
    )
    return extractor.extract(text, low_confidence_items)
