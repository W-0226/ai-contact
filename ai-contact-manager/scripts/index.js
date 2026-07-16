/**
 * AI人脉关系管家 — Node.js 包装入口
 *
 * 作为 Node.js 生态的入口点，封装 Python 核心脚本的调用。
 * 适用于希望从 Node.js 应用或 CLI 中调用本技能的场景。
 *
 * 用法：
 *   node index.js --input ../data/sample_notes.txt --mode local
 *   node index.js --input ../data/sample_notes.txt --mode hybrid --llm-api-key sk-xxx
 */

const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

// ========== CLI 参数解析 ==========

function parseArgs() {
  const args = process.argv.slice(2);
  const options = {
    input: null,
    text: null,
    mode: "local",
    llmProvider: "deepseek",
    llmApiKey: null,
    llmModel: null,
    llmBaseUrl: null,
    outputDir: "outputs",
    maxReminders: 10,
    rules: null,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    const next = args[i + 1];

    switch (arg) {
      case "--input":
      case "-i":
        options.input = next;
        i++;
        break;
      case "--text":
      case "-t":
        options.text = next;
        i++;
        break;
      case "--mode":
      case "-m":
        options.mode = next;
        i++;
        break;
      case "--llm-provider":
        options.llmProvider = next;
        i++;
        break;
      case "--llm-api-key":
        options.llmApiKey = next;
        i++;
        break;
      case "--llm-model":
        options.llmModel = next;
        i++;
        break;
      case "--llm-base-url":
        options.llmBaseUrl = next;
        i++;
        break;
      case "--output-dir":
      case "-o":
        options.outputDir = next;
        i++;
        break;
      case "--max-reminders":
        options.maxReminders = parseInt(next, 10);
        i++;
        break;
      case "--rules":
        options.rules = next;
        i++;
        break;
      case "--input-type":
        options.inputType = next;
        i++;
        break;
      case "--ocr-gpu":
        options.ocrGpu = true;
        break;
      case "--ocr-lang":
        options.ocrLang = next;
        i++;
        break;
      case "--asr-model-size":
        options.asrModelSize = next;
        i++;
        break;
      case "--asr-gpu":
        options.asrGpu = true;
        break;
      case "--help":
      case "-h":
        printHelp();
        process.exit(0);
      default:
        // 忽略未知参数
        break;
    }
  }

  return options;
}

function printHelp() {
  console.log(`
AI人脉关系管家 — Node.js 包装入口

用法:
  node index.js --input <文件> --mode <模式> [选项]

选项:
  --input, -i <path>       输入文件路径（文本/图片/音频）
  --text, -t <text>        直接输入文本
  --input-type <type>      输入类型: text | image | audio | auto (默认: auto)
  --mode, -m <mode>        提取模式: local | llm | hybrid (默认: local)
  --llm-provider <name>    LLM 提供商: openai | deepseek | custom
  --llm-api-key <key>      LLM API 密钥
  --llm-model <name>       模型名称
  --llm-base-url <url>     自定义 API 端点
  --ocr-gpu                OCR 使用 GPU 加速
  --ocr-lang <lang>        OCR 语言 (默认: ch)
  --asr-model-size <size>  Whisper 模型: tiny|base|small|medium (默认: base)
  --asr-gpu                ASR 使用 GPU 加速
  --output-dir, -o <dir>   输出目录 (默认: outputs)
  --max-reminders <n>      最大提醒条数 (默认: 10)
  --rules <path>           自定义规则文件路径
  --help, -h               显示此帮助信息
`);
}

// ========== Python 调用 ==========

async function runPython(options) {
  const scriptDir = __dirname;
  const pythonScript = path.join(scriptDir, "extract_contacts.py");

  if (!fs.existsSync(pythonScript)) {
    console.error(`错误: 找不到 Python 脚本: ${pythonScript}`);
    process.exit(1);
  }

  // 构建参数
  const pythonArgs = [pythonScript];

  if (options.input) {
    pythonArgs.push("--input", options.input);
  }
  if (options.text) {
    pythonArgs.push("--text", options.text);
  }
  pythonArgs.push("--mode", options.mode);
  pythonArgs.push("--output-dir", options.outputDir);
  pythonArgs.push("--max-reminders", String(options.maxReminders));

  if (options.llmApiKey) {
    pythonArgs.push("--llm-api-key", options.llmApiKey);
  }
  if (options.llmProvider) {
    pythonArgs.push("--llm-provider", options.llmProvider);
  }
  if (options.llmModel) {
    pythonArgs.push("--llm-model", options.llmModel);
  }
  if (options.llmBaseUrl) {
    pythonArgs.push("--llm-base-url", options.llmBaseUrl);
  }
  if (options.rules) {
    pythonArgs.push("--rules", options.rules);
  }

  // 查找 Python 解释器
  const pythonCmd = findPython();
  console.log(`>>> ${pythonCmd} ${pythonArgs.join(" ")}`);

  return new Promise((resolve, reject) => {
    const proc = spawn(pythonCmd, pythonArgs, {
      cwd: scriptDir,
      stdio: "inherit",
      env: { ...process.env, PYTHONIOENCODING: "utf-8" },
    });

    proc.on("close", (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`Python 进程退出码: ${code}`));
      }
    });

    proc.on("error", (err) => {
      reject(new Error(`无法启动 Python: ${err.message}`));
    });
  });
}

function findPython() {
  // 按优先级尝试
  const candidates = process.platform === "win32"
    ? ["python", "python3", "py"]
    : ["python3", "python"];

  // 仅返回命令名，spawn 会用 PATH 查找
  return candidates[0];
}

// ========== 主入口 ==========

async function main() {
  const options = parseArgs();

  if (!options.input && !options.text) {
    console.error("错误: 需要提供 --input 或 --text 参数。");
    console.error("使用 --help 查看帮助。");
    process.exit(1);
  }

  if ((options.mode === "llm" || options.mode === "hybrid") && !options.llmApiKey) {
    console.warn("⚠️  警告: LLM/hybrid 模式但没有提供 --llm-api-key，将降级为本地模式。");
    options.mode = "local";
  }

  try {
    await runPython(options);
    console.log("\n✅ Node.js 包装调用完成。");
  } catch (err) {
    console.error(`\n❌ 执行失败: ${err.message}`);
    process.exit(1);
  }
}

main();
