# AI人脉关系管家 — 迭代记录

> 项目：AI人脉关系管家 Skill
> 作者：wu241010268
> 日期：2026年7月15日 - 7月16日

---

## 迭代一：Skill 目录结构与核心提取引擎（7/15 下午）

### 目标
搭建完整的 Skill 项目骨架，实现从散乱聊天备注中提取联系人信息。

### 新增文件
```
ai-contact-manager/
├── SKILL.md                         ← 技能说明书（YAML 头信息 + 完整文档）
├── scripts/
│   ├── extract_contacts.py          ← 主入口（local/hybrid/llm 三种模式）
│   ├── local_extractor.py           ← 本地规则引擎（正则 + 关键词）
│   ├── llm_extractor.py             ← LLM 增强引擎（OpenAI/DeepSeek 兼容）
│   ├── generate_reminders.py        ← 提醒生成器（JSON + Markdown 双输出）
│   └── index.js                     ← Node.js 包装入口
├── references/
│   ├── extraction_rules.json        ← 提取规则配置（可热更新）
│   ├── prompt_templates.md          ← LLM 提示词模板库
│   └── output_schema.json           ← 输出格式 JSON Schema
└── data/
    └── sample_notes.txt             ← 6条测试基准数据
```

### 设计决策
- 提取策略：混合模式（本地规则优先 + LLM 增强），置信度 < 0.6 的条目自动送 LLM
- 输出格式：JSON（结构化） + Markdown（可读报告）双输出
- 脚本语言：Python 核心 + Node.js 包装
- 版本号：v1.0.0

### 核心能力
| 提取维度 | 方法 | 示例 |
|----------|------|------|
| 姓名 | 称呼模式 + 中文姓名 | 老王、张总、Mike |
| 生日 | 正则（公历/农历/模糊） | 3月15号、腊月初八 |
| 爱好 | 关键词词典 + "喜欢X"模式 | 钓鱼、乒乓球 |
| 关键事件 | 关键词 + 日期定位 | 7月聊跨境电商 |
| 标签 | 关键词匹配 | 已婚、程序员 |

---

## 迭代二：测试数据集与输出样本（7/15 下午）

### 目标
生成测试数据、输出样本，支持后续验证。

### 新增文件
```
data/
└── simulated_contacts_100.txt       ← 约100条模拟数据

outputs/
├── contacts_sample.json             ← 结构化输出样本
└── contacts_sample.md               ← 可读报告样本
```

### 模拟数据覆盖
- 30+ 种职业：程序员/医生/律师/设计师/空姐/外卖骑手…
- 15+ 种认识渠道：大学同学/前同事/邻居/健身房/峰会/宠物展…
- 生日类型：明确公历 / 模糊月份 / 农历 / 节日关联 / 缺失
- 关键事件：换工作、考研、结婚、创业融资、宠物、疾病…

---

## 迭代三：单元测试与 Bug 修复（7/15 傍晚）

### 目标
建立测试框架，发现并修复代码缺陷。

### 新增文件
```
pytest.ini                         ← 测试配置
tests/
├── conftest.py                     ← 共用夹具（10个fixture）
├── test_local_extractor.py         ← 43个本地引擎测试
└── test_generate_reminders.py      ← 18个提醒生成器测试
```

### 修复的 Bug
| 问题 | 修复前 | 修复后 |
|------|--------|--------|
| last_time_pattern 正则过严 | "上次5月吃饭"不匹配 | 日期后缀改为可选 |
| 日期不支持年份 | "2026年5月"解析失败 | 新增年份前缀解析 |
| 爱好重复 | 正则+关键词重复抓取 | 关键词优先，regex去重 |
| "经常X"误识别 | "经常发朋友圈"被当爱好 | 从模式中移除"经常" |
| "去年X月"不识别 | 仅匹配"上次/上回" | 扩展为"去年/前年/上个月" |

### 测试结果
```
61 passed, 0 failed
```

---

## 迭代四：多格式输入支持（7/15 晚间）

### 目标
支持文本、图片（聊天截图）、音频（录音）三种输入方式。

### 新增文件
```
scripts/
├── ocr_extractor.py                ← PaddleOCR 图片文字提取
└── asr_extractor.py                ← Whisper 语音转文字
```

### 修改文件
```
scripts/extract_contacts.py          ← 新增 --input-type 参数 + 自动检测
scripts/index.js                     ← 新增 OCR/ASR 参数传递
SKILL.md                             ← 更新 inputs/outputs 描述，v1.1.0
```

### 导入方式
```bash
# 自动检测
python extract_contacts.py -i screenshot.png  → OCR
python extract_contacts.py -i recording.mp3   → ASR

# 手动指定
python extract_contacts.py -i file.jpg --input-type image --ocr-gpu
python extract_contacts.py -i voice.m4a --input-type audio --asr-model-size tiny
```

---

## 迭代五：关系价值评分与断联预警（7/16 上午）

### 目标
从"机械提醒"升级到"关系洞察"——判断关系价值、预警断联并提供方案。

### 新增文件
```
scripts/relationship_analyzer.py     ← 关系价值评分 + 断联分析
tests/test_relationship_analyzer.py  ← 15个关系分析测试
```

### 核心机制

#### 四维价值评分（0-100）
| 维度 | 权重 | 评分依据 |
|------|:----:|----------|
| 信息完整度 | 25 | 生日+10, 爱好/事件/标签各+5 |
| 关系亲密度 | 25 | 家人25 > 室友18 > 同事15 > 峰会3 |
| 联系质量 | 25 | 近期联系+7, 从未联系-5 |
| 潜在价值 | 25 | CEO/融资等信号x4, 经理等x2 |

#### 五级断联状态
```
活跃(≤30天) → 变冷(30-90天) → 冻结(90-365天) → 深度冻结(>365天) → 💀僵尸(从未联系)
```

#### 报告新增章节
- 📊 关系价值分析：价值分布 + Top 10 排行榜（四维雷达）+ 亮点/弱点
- 🚨 断联预警：原因诊断（含置信度）+ 破冰话术 + 时机建议 + 放手提醒

### 测试结果
```
76 passed, 0 failed
```

---

## 迭代六：隐私保护与关系确认队列（7/16 上午）

### 目标
1. 保护人脉数据隐私，仅用户本人可访问
2. 数据入库后自动检测模糊关系，提供方案供用户选择

### 新增文件
```
scripts/
├── privacy_manager.py               ← AES-256 加密 + 权限控制
└── review_queue.py                  ← 关系确认队列生成

tests/
└── test_privacy_and_review.py       ← 14个隐私与确认测试
```

### 隐私保护能力
| 功能 | 实现 |
|------|------|
| 加密算法 | AES-256-CBC + PBKDF2（100000次迭代） |
| 密码强度 | 自动评分（弱/中/强）+ 改进建议 |
| 锁定/解锁 | `--encrypt --password "xxx"` |
| 访问日志 | JSON 行格式，记录每次加解密操作 |
| 分享令牌 | 提取单联系人 + 临时随机密码加密 |

```bash
# 加密输出
python extract_contacts.py -i data.txt -m local --encrypt --password "MyP@ss2026!"

# 跳过确认队列
python extract_contacts.py -i data.txt --no-review-queue
```

### 关系确认队列 — 六类检测规则
| 规则 | 触发条件 | 示例 |
|------|----------|------|
| 关系类型不明 | 无标签 + 无关系词 | "和王总是什么关系？" 4选1 |
| 生日缺失/模糊 | 无生日或农历未确认 | 王阿姨腊月初八需确认 |
| 高价值但信息空白 | CEO/CTO 但一无所知 | 赵总：CTO+零信息 |
| 断联原因不明 | 长期未联系+无上下文 | 自然疏远 vs 暂时忙 vs 关系降温 |
| 破冰障碍 🔴 | 备注中提到想联系但无策略 | 5种切入方案供选择 |
| 基础信息全空 | 三项基本信息全无 | 翻朋友圈/聊天记录/下次问 |

每条提供 2-5 个可选方案，标记紧急程度，输出 `REVIEW_QUEUE.md`。

### 测试结果
```
90 passed, 0 failed
```

---

## 当前版本总览

| 项目 | 详情 |
|------|------|
| 版本号 | v1.2.0 |
| 测试覆盖 | 90 个单元测试，全部通过 |
| 脚本模块 | 8 个 Python + 1 个 Node.js |
| 支持输入 | 文本直读 / 图片OCR / 音频ASR |
| 提取模式 | local / llm / hybrid |
| 输出格式 | JSON + Markdown |
| 分析能力 | 价值评分 / 断联预警 / 关系确认 |
| 安全能力 | AES-256加密 / 密码保护 / 分享令牌 |

### 完整文件清单
```
ai-contact-manager/
├── SKILL.md                          ← v1.2.0
├── pytest.ini
├── scripts/
│   ├── extract_contacts.py           ← 主入口（多格式 + 加密 + 确认队列）
│   ├── local_extractor.py            ← 本地规则提取引擎
│   ├── llm_extractor.py              ← LLM 增强提取引擎
│   ├── ocr_extractor.py              ← PaddleOCR 图片文字提取
│   ├── asr_extractor.py              ← Whisper 语音转文字
│   ├── generate_reminders.py         ← 提醒生成器（含关系分析）
│   ├── relationship_analyzer.py      ← 关系价值评分 + 断联分析
│   ├── privacy_manager.py            ← AES-256 加密 + 权限控制
│   ├── review_queue.py               ← 关系确认队列生成
│   └── index.js                      ← Node.js 包装入口
├── references/
│   ├── extraction_rules.json         ← 提取规则配置
│   ├── prompt_templates.md           ← LLM 提示词模板
│   └── output_schema.json            ← 输出格式规范
├── tests/
│   ├── conftest.py
│   ├── test_local_extractor.py       ← 43 tests
│   ├── test_generate_reminders.py    ← 20 tests
│   ├── test_relationship_analyzer.py ← 15 tests
│   └── test_privacy_and_review.py    ← 14 tests
├── data/
│   ├── sample_notes.txt              ← 6条测试基准
│   └── simulated_contacts_100.txt    ← 约100条模拟数据
├── outputs/
│   ├── contacts_sample.json          ← 输出格式样本
│   ├── contacts_sample.md            ← 输出格式样本
│   ├── test_case_01_老王.md          ← 测试记录
│   └── test_case_02_赵总.md          ← 测试记录
└── iteration/
    └── iteration_log.md              ← 本文件
```

---

## 迭代七：标准化目录结构（7/16 上午）

### 目标
按标准 Skill 目录结构整理项目，明确各文件夹职责。

### 调整内容
```
ai-contact-manager/
├── README.md                         ← 项目说明（选题/功能/使用方式）
├── SKILL.md
├── pytest.ini
├── scripts/
├── references/
├── data/
├── tests/                            ← 测试代码 + 测试执行记录
│   ├── conftest.py
│   ├── test_*.py
│   └── test_record.md                ← 原 iteration/test_report.md 移入
├── outputs/                          ← 运行时输出
└── iteration/
    └── iteration_log.md              ← 仅保留迭代记录
```

### 标准结构对照表

| 文件夹 | 职责 | 本项目内容 |
|--------|------|------------|
| SKILL.md | 技能定义（含 yaml 前端配置） | ✅ |
| scripts/ | 脚本/工具代码 | 10 个 Python + 1 个 Node.js |
| references/ | 参考文件/配置文件 | 3 个配置文件 |
| data/ | 测试数据 | 2 个测试文件 |
| tests/ | 测试代码 + 测试记录 | 5 个测试文件 + test_record.md |
| iteration/ | 迭代升级说明 | iteration_log.md |
| README.md | 项目说明（选题/功能/使用方式） | ✅ |
