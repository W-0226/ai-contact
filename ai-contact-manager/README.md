# AI人脉关系管家

> 把散乱的聊天备注、截图、录音，交给 AI 自动整理成结构化联系人档案，  
> 让你再也不会忘记谁是谁、错过重要日子、见面想不起上次聊什么。

---

## 一、选题背景

### 痛点

职场人、商务人士、学生会成员、社交达人…大家都有人脉管理的三大困扰：

| 痛点 | 表现 | 频率 |
|------|------|------|
| **忘了谁是谁** | 加上微信只记得脸，分不清是同事、客户还是同学 | 高 |
| **重要日子忘祝福** | 朋友生日、结婚纪念日，一不留神就错过 | 高 |
| **见面想不起上次聊什么** | 寒暄完就冷场，不知道从哪切入 | 中 |

### 解决方案

一个本地优先、可扩展的 AI 工具，**输入即用、输出即提醒、关系能洞察、隐私有保障**。

---

## 二、功能简介

### 核心能力（v1.2.0）

```
┌────────────────────────────────────────────────────────┐
│                                                        │
│  多种输入 → 智能提取 → 关系洞察 → 联系提醒 → 隐私保护  │
│                                                        │
└────────────────────────────────────────────────────────┘
```

| 模块 | 功能 | 状态 |
|------|------|:----:|
| 📝 文本提取 | 解析散乱备注，提取姓名/生日/爱好/关键事件 | ✅ |
| 🖼️ 图片OCR | 聊天截图、名片图片 → 文字 → 联系人 | ✅ PaddleOCR |
| 🎤 语音ASR | 录音、语音消息 → 文字 → 联系人 | ✅ Whisper |
| 🤖 LLM 增强 | 低置信度条目自动送 LLM 补全 | ✅ OpenAI/DeepSeek |
| 📊 关系评分 | 四维度评估（信息/亲密/联系/潜力） | ✅ 0-100 分 |
| 🚨 断联预警 | 五级状态分级 + 原因诊断 + 行动方案 | ✅ |
| 📋 确认队列 | 模糊关系自动检测，提供方案供用户选择 | ✅ 6 类规则 |
| 🔒 隐私保护 | AES-256 加密 + 密码保护 + 访问日志 | ✅ |
| 🔗 分享令牌 | 单个联系人加密分享 | ✅ |

### 输入支持

- **文本**：`sample_notes.txt` 备注文件
- **图片**：聊天截图、名片、朋友圈截图（自动检测 `.jpg/.png` 等）
- **音频**：录音、微信语音、播客片段（自动检测 `.mp3/.m4a` 等）

### 输出格式

- `contacts.json` — 结构化联系人数据
- `reminders.md` — 可读联系提醒报告（含关系分析、断联预警、破冰建议）
- `reminders.json` — 机器可读的提醒数据
- `REVIEW_QUEUE.md` — 关系确认队列（待用户回答的问题）
- `extraction_log.json` — 提取过程日志

---

## 三、使用方式

### 1. 命令行使用

```bash
# 文本输入（默认模式）
python extract_contacts.py -i data/sample_notes.txt -m local

# 图片输入（聊天截图）
python extract_contacts.py -i screenshot.png -m local

# 音频输入（录音）
python extract_contacts.py -i recording.mp3 -m local

# 混合模式（本地 + LLM 增强）
python extract_contacts.py -i data.txt -m hybrid --llm-api-key sk-xxx

# 加密输出
python extract_contacts.py -i data.txt --encrypt --password "MyP@ss2026!"

# 生成加密的单个联系人分享
python -c "from privacy_manager import PrivacyManager; \
  pm = PrivacyManager('outputs'); \
  pm.generate_share_token('outputs/contacts.json.enc', 'mypassword', '张三')"
```

### 2. Node.js 包装

```bash
node scripts/index.js -i data.txt -m local
```

### 3. 在 WorkBuddy 中调用

将本目录作为 Skill 安装到 WorkBuddy，在对话中输入：

> 「帮我分析这段聊天备注：[粘贴文本]」

### 4. 完整参数

```bash
python extract_contacts.py --help
```

主要参数：
- `-i, --input` — 输入文件路径（必填）
- `--input-type` — text/image/audio/auto（默认 auto）
- `-m, --mode` — local/llm/hybrid（默认 local）
- `--encrypt --password` — 加密输出
- `--no-review-queue` — 跳过确认队列生成
- `-o, --output-dir` — 输出目录（默认 outputs）

---

## 四、目录结构

```
ai-contact-manager/
├── SKILL.md                      ← 技能定义（含 yaml 前端配置）
├── README.md                     ← 项目说明（本文件）
├── pytest.ini                    ← 测试配置
│
├── scripts/                      ← 脚本/工具代码
│   ├── extract_contacts.py       ← 主入口（多格式输入）
│   ├── local_extractor.py        ← 本地规则引擎
│   ├── llm_extractor.py          ← LLM 增强引擎
│   ├── ocr_extractor.py          ← PaddleOCR 图片文字提取
│   ├── asr_extractor.py          ← Whisper 语音转文字
│   ├── generate_reminders.py     ← 提醒生成器
│   ├── relationship_analyzer.py  ← 关系价值评分 + 断联分析
│   ├── privacy_manager.py        ← AES-256 加密 + 权限控制
│   ├── review_queue.py           ← 关系确认队列
│   └── index.js                  ← Node.js 包装入口
│
├── references/                   ← 参考文件/配置
│   ├── extraction_rules.json     ← 提取规则配置
│   ├── prompt_templates.md       ← LLM 提示词模板
│   └── output_schema.json        ← 输出 JSON Schema
│
├── data/                         ← 测试数据
│   ├── sample_notes.txt          ← 6 条测试基准
│   └── simulated_contacts_100.txt← 100 条模拟数据
│
├── tests/                        ← 测试代码 + 记录
│   ├── conftest.py               ← pytest 共用夹具
│   ├── test_local_extractor.py   ← 38 个本地引擎测试
│   ├── test_generate_reminders.py← 20 个提醒测试
│   ├── test_relationship_analyzer.py ← 15 个关系分析测试
│   ├── test_privacy_and_review.py← 17 个隐私/确认测试
│   └── test_record.md            ← 完整测试执行记录
│
├── outputs/                      ← 运行时输出（脚本生成）
│   ├── contacts.json             ← 结构化联系人数据
│   ├── contacts.json.enc         ← 加密版
│   ├── contacts_sample.*         ← 输出格式样本
│   ├── reminders.md              ← 提醒报告
│   ├── reminders.json
│   ├── REVIEW_QUEUE.md           ← 关系确认队列
│   ├── extraction_log.json
│   ├── access.log                ← 访问日志
│   └── test_case_*.md            ← 测试记录
│
└── iteration/                    ← 迭代升级说明
    └── iteration_log.md          ← 六轮迭代详细记录
```

---

## 五、技术栈

| 类别 | 选型 |
|------|------|
| 核心语言 | Python 3.13 |
| 测试框架 | pytest 9.1 |
| 加密 | pycryptodome（AES-256-CBC） |
| OCR | PaddleOCR（可选） |
| ASR | OpenAI Whisper（可选） |
| LLM | OpenAI / DeepSeek 兼容 API（可选） |
| 包装层 | Node.js |

### 安装依赖

```bash
# 基础依赖（local 模式 + 测试）
pip install python-dateutil lunardate pytest pycryptodome

# OCR（可选）
pip install paddlepaddle paddleocr

# ASR（可选）
pip install openai-whisper

# LLM（可选）
pip install openai
```

---

## 六、性能指标

| 指标 | 实测值 |
|------|--------|
| 单元测试 | **90 / 90 全部通过** |
| 测试执行时间 | 0.80 秒 |
| 处理速度 | 6 联系人 < 0.1 秒（local 模式） |
| 100 条数据处理 | < 1 秒 |
| 加密 1MB 文件 | < 0.1 秒 |

---

## 七、设计理念

1. **本地优先**：不联网、不上传、无外部依赖就能跑
2. **可扩展**：规则可热更新，引擎可替换
3. **隐私第一**：默认纯本地，敏感数据可加密
4. **诚实**：低置信度明确标注，不编造信息
5. **可解释**：所有提取和评分都基于规则，可审计
6. **模块化**：每个模块独立可测，便于扩展

---

## 八、版本历史

完整迭代记录见 [iteration/iteration_log.md](./iteration/iteration_log.md)

| 版本 | 日期 | 核心能力 |
|------|------|----------|
| v1.0.0 | 2026-07-15 | Skill 骨架 + 核心提取引擎 |
| v1.1.0 | 2026-07-15 | OCR + ASR 多格式输入 |
| v1.2.0 | 2026-07-16 | 关系分析 + 断联预警 + 隐私保护 + 确认队列 |

---

## 九、作者

**wu241010268**

2026 年嘉应学院课程作业

---

*使用本 Skill 即表示你已了解：所有数据处理优先在本地完成，加密选项需自行管理密码。*
