---
name: ai-contact-manager
description: >
  AI人脉关系管家 — 将散乱的聊天备注智能转化为结构化联系人档案。
  支持文本、图片（OCR）、音频（ASR）三种输入格式，
  自动提取生日、爱好、关键事件等信息，
  并基于时间轴生成联系提醒。采用混合模式：本地规则引擎（正则+
  关键词）优先，可选接入 LLM 增强语义理解。
version: 1.1.0
author: wu241010268
inputs:
  chat_notes:
    type: string
    required: true
    description: >
      用户输入的散乱聊天备注文本。可包含多条联系人信息。
      支持三种导入方式：
      - 文本直读：.txt / .md 文件或 --text 参数
      - 图片 OCR：聊天截图、名片、照片（PaddleOCR）
      - 语音 ASR：录音、语音消息（Whisper）
  input_type:
    type: string
    required: false
    default: auto
    description: >
      输入类型。auto = 根据文件后缀自动检测；
      text/image/audio = 手动指定类型。
  mode:
    type: string
    required: false
    default: hybrid
    description: >
      提取模式。
      - "local": 仅使用本地规则引擎（关键词匹配 + 正则）
      - "llm": 仅使用 LLM API 进行语义提取
      - "hybrid": 本地规则优先，仅在置信度不足时调用 LLM 增强
  llm_config:
    type: object
    required: false
    description: >
      LLM API 配置对象。仅在 mode 为 "llm" 或 "hybrid" 时需要。
  ocr_config:
    type: object
    required: false
    description: >
      OCR 配置。use_gpu（GPU加速）、lang（语言，ch=中英混合）。
  asr_config:
    type: object
    required: false
    description: >
      ASR 配置。model_size（tiny/base/small/medium/large）、
      language（zh/en）、use_gpu。
  max_reminders:
    type: integer
    required: false
    default: 10
    description: 生成提醒的最大条数。
outputs:
  contacts_json:
    type: file
    path: outputs/contacts.json
    description: >
      结构化联系人数据，JSON 格式。每个联系人包含：
      name, aliases, birthday（ISO 8601 日期），
      hobbies（字符串数组），key_events（含日期和描述的对象数组），
      tags, notes, confidence（提取置信度 0-1），
      source（标注数据来源：local / llm / hybrid），
      input_source（标注输入来源：text_file / ocr / asr）。
  reminders_md:
    type: file
    path: outputs/reminders.md
    description: >
      人类可读的联系提醒报告，Markdown 格式。包含：
      近期生日提醒、定期联络建议、关键事件时间线、
      基于兴趣的沟通话题推荐。
  extraction_log:
    type: file
    path: outputs/extraction_log.json
    description: >
      提取过程日志，记录每条信息的提取方式、置信度、
      匹配规则或 LLM 调用详情，便于调试和审计。
---

# AI人脉关系管家 — 技能说明

## 概述

你是否有过这样的困扰：微信里加了很多人，备注里记了零碎的聊天片段，但时间一长就忘了谁是谁、该什么时候联系谁？

本技能解决的核心问题：**非结构化聊天备注 → 结构化联系人档案 + 智能联系提醒**。

## 适用场景

- 商务社交：记录客户的兴趣、合作意向、关键会议时间
- 日常社交：记住朋友的生日、共同话题、上次见面时间
- 社群运营：管理成员的关键信息和互动节奏
- 任何人脉密集、需要定期维护关系的场景

## 工作流程

```
用户输入（散乱备注）
    │
    ▼
┌─────────────────────────┐
│  1. 文本预处理           │
│  - 分段/分条             │
│  - 联系人名识别          │
│  - 去噪                  │
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│  2. 信息提取（混合引擎）  │
│  ┌─────────────────┐    │
│  │ 本地规则引擎     │    │
│  │ - 日期正则      │    │
│  │ - 关键词词典    │    │
│  │ - 模式匹配      │    │
│  └────────┬────────┘    │
│           │ 低置信度    │
│           ▼             │
│  ┌─────────────────┐    │
│  │ LLM 增强引擎    │    │
│  │ - 语义理解      │    │
│  │ - 隐性信息推断  │    │
│  └─────────────────┘    │
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│  3. 结构化输出           │
│  - contacts.json        │
│  - reminders.md         │
│  - extraction_log.json  │
└─────────────────────────┘
```

## 使用方法

### 命令行 — 文本输入

```bash
cd scripts
python extract_contacts.py -i ../data/sample_notes.txt -m local
```

### 命令行 — 图片输入（聊天截图 / 名片）

```bash
# 自动检测图片格式 → 走 OCR
python extract_contacts.py -i screenshot.png -m local

# 手动指定 + GPU 加速
python extract_contacts.py -i business_card.jpg --input-type image --ocr-gpu -m local
```

### 命令行 — 音频输入（录音 / 语音消息）

```bash
# 自动检测音频格式 → 走 ASR
python extract_contacts.py -i recording.mp3 -m local

# 用小模型快速转写
python extract_contacts.py -i voice.m4a --input-type audio --asr-model-size tiny -m local
```

### 混合模式（本地 + LLM 增强）

```bash
python extract_contacts.py -i screenshot.png -m hybrid --llm-api-key sk-xxx
```

### Node.js 包装入口

```bash
cd scripts
node index.js --input ../data/screenshot.png --mode local

### 作为 Skill 被 WorkBuddy 调用

在 WorkBuddy 对话中直接使用：

> 帮我分析这段聊天备注：[粘贴文本]

Skill 会自动加载，按配置的默认模式执行。

## 输入文本格式示例

```
老王，3月15号生日，属兔，喜欢钓鱼和打乒乓球。
上次7月初聊到他在做跨境电商，主要做东南亚市场。
他老婆叫小李，孩子刚上小学。

张总，公司是做工业设计的，上次12月20号吃饭，
提到明年3月有个大项目要合作。
他喜欢喝普洱，对茶道很有研究。生日好像是8月还是9月。

李明，大学同学，程序员，单身。
7月5号刚换了工作去字节。
喜欢打篮球和看科幻电影。
```

## 输出示例

### contacts.json（摘要）

```json
{
  "contacts": [
    {
      "name": "老王",
      "birthday": "03-15",
      "hobbies": ["钓鱼", "乒乓球"],
      "key_events": [
        {
          "date": "2026-07",
          "description": "聊到在做跨境电商（东南亚市场）"
        }
      ],
      "tags": ["创业者", "已婚", "有孩子"],
      "confidence": 0.92,
      "source": "local"
    }
  ],
  "generated_at": "2026-07-15T15:56:01+08:00"
}
```

### reminders.md（摘要）

```markdown
# 📇 人脉联系提醒

## 🎂 近期生日（30天内）
| 联系人 | 生日 | 距今天数 | 建议 |
|--------|------|----------|------|
| 老王 | 3月15日 | 243天 | 设为年度提醒 |

## 📞 建议近期联系
| 联系人 | 上次联系 | 建议联系时间 | 话题 |
|--------|----------|-------------|------|
| 张总 | 12月20日 | 建议3月前联系 | 大项目合作 |
| 李明 | 7月5日 | 建议8月初联系 | 新工作适应情况 |
```

## 目录结构

```
ai-contact-manager/
├── SKILL.md                      # 本文件（技能说明）
├── pytest.ini                    # 测试配置
├── scripts/                      # 可执行脚本
│   ├── extract_contacts.py       # 主入口（多格式支持）
│   ├── local_extractor.py        # 本地规则提取引擎
│   ├── llm_extractor.py          # LLM 增强提取引擎
│   ├── ocr_extractor.py          # 🆕 PaddleOCR 图片文字提取
│   ├── asr_extractor.py          # 🆕 Whisper 语音转文字
│   ├── generate_reminders.py     # 提醒生成器
│   └── index.js                  # Node.js 包装入口
├── references/                   # 参考配置与文档
│   ├── extraction_rules.json     # 本地规则配置
│   ├── prompt_templates.md       # LLM 提示词模板
│   └── output_schema.json        # 输出格式规范
├── tests/                        # 🆕 单元测试
│   ├── conftest.py               # 共用夹具
│   ├── test_local_extractor.py   # 本地引擎测试（43个）
│   └── test_generate_reminders.py # 提醒生成器测试（18个）
├── outputs/                      # 输出样本与测试记录
└── data/                         # 测试数据
    ├── sample_notes.txt          # 6条测试基准
    └── simulated_contacts_100.txt # 100条模拟数据
```

## 依赖

### 核心依赖（local 模式即可运行）

```txt
python-dateutil>=2.8.2     # 日期解析
lunardate>=0.2.0           # 农历日期支持
```

### 多格式输入依赖（按需安装）

```txt
# 图片 OCR（聊天截图 / 名片识别）
paddlepaddle>=2.6.0        # CPU 版本
paddleocr>=2.7.0           # OCR 引擎

# 语音 ASR（录音转文字）
openai-whisper>=20231117   # 语音转文字引擎
```

### LLM 增强依赖（hybrid / llm 模式需要）

```txt
openai>=1.0.0              # OpenAI / DeepSeek 兼容 API
```

### 测试依赖

```txt
pytest>=8.0.0              # 测试框架
```

## 注意事项

1. **隐私第一**：所有提取过程默认在本地运行，仅在用户明确开启 LLM 模式时才会将文本发送至 API。
2. **置信度标注**：每条提取结果都附带 `confidence` 字段，用户可自行审核低置信度结果。
3. **农历支持**：输入中的农历日期（如"腊月初八"）会被标注并记录，提醒生成时同时考虑公历和农历。
4. **可扩展性**：`extraction_rules.json` 中的规则可按需增删，无需修改代码。
