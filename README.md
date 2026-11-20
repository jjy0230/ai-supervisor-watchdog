# AI Supervisor Watchdog (智能体监督与推进工作台)

一套轻量级、零/极低 Token 消耗的**外部 Supervisor 智能体守护系统**。它监听桌面 AI 应用（如 Cursor、VS Code）或命令行智能体（如 Aider、Claude Code）的运行状态，在干活 AI（Worker）停顿或声称完成时，结合人类预设的任务清单（`tasks.md`）与真实代码库物理事实进行严苛审计，自动注入纠偏指令或放行推进到下一步。

---

## 核心架构设计

```
                         [ 你的任务清单: tasks.md ]
                                     |
                                     v
+--------------------------------------------------------------------------+
| 1. 停滞感知层 (Drivers - 零 Token 轮询)                                   |
|    • DesktopDriver: 基于 Windows 原生 UI Automation 监听输入框与生成按钮  |
|    • CLIDriver: 监听子进程管道输出与静默时长                              |
|    • MockDriver: 离线自动化测试与全链路仿真                              |
+--------------------------------------------------------------------------+
                                     | 捕获停滞事件
                                     v
+--------------------------------------------------------------------------+
| 2. 物理事实与拓扑感知层 (Sensors & RepoMap - 零 Token 本地运行)             |
|    • CodebaseSensor: 自动运行 `git diff --stat`、语法编译与单元测试 (`pytest`)|
|    • RepoMap: 借鉴 Aider/grep-ast 设计，用 AST 提取代码骨架 (<1000 Token) |
+--------------------------------------------------------------------------+
                                     | 打包事实证据
                                     v
+--------------------------------------------------------------------------+
| 3. 非对称仲裁决策层 (Arbiter & Circuit Breaker)                           |
|    • ArbiterEngine: 支持 Claude 3.5 Sonnet / DeepSeek / 本地 Ollama        |
|    • 裁决输出: [PASS] 勾选清单推进 | [RETRY] 携证据纠偏 | [BLOCKED] 报警人工  |
|    • CircuitBreaker: 循环检测 (相似度 > 85%) 与单任务重试上限 (3次) 紧急熔断|
+--------------------------------------------------------------------------+
                                     | 下发决策动作
                                     v
+--------------------------------------------------------------------------+
| 4. 动作注入层 (ValuePattern.SetValue / PTY.write)                        |
|    • 自动将纠偏或下一阶段指令写入目标对话框并提交，驱动 Worker 继续干活    |
+--------------------------------------------------------------------------+
```

---

## 项目目录结构

```text
ai-supervisor-watchdog/
├── config.yaml               # 核心配置文件 (驱动模式、模型、传感器配置)
├── tasks.md                  # 人类意图清单 (Markdown Checkboxes)
├── requirements.txt          # Python 依赖
├── supervisor/
│   ├── config.py             # 配置解析器
│   ├── engine.py             # 调度器主引擎
│   ├── cli.py                # 命令行交互工具
│   ├── core/
│   │   ├── tasks.py          # tasks.md 解析器与状态机
│   │   ├── repomap.py        # 基于 AST 的代码库骨架提取器 (借鉴 Aider)
│   │   ├── linter.py         # 物理传感器 (Git Diff / 语法检查 / 测试执行)
│   │   ├── arbiter.py        # 仲裁模型接入层 (Prompt 约束输出)
│   │   └── circuit_breaker.py# 防死锁与死循环熔断器
│   └── drivers/
│       ├── base.py           # 抽象驱动基类
│       ├── desktop_driver.py # Windows UI Automation 驱动
│       ├── cli_driver.py     # 命令行子进程驱动
│       └── mock_driver.py    # 离线仿真驱动
└── tests/                    # 单元测试与端到端模拟测试套件
```

---

## 快速上手与操作指南

### 1. 环境准备
已包含 Windows 原生支持，安装基础依赖：
```bash
pip install -r requirements.txt
```

### 2. 常用命令

#### ① 检查代码库与传感器状态（零 Token 预览）
查看当前 `tasks.md` 进度、Git 变更以及系统提取的 RepoMap 骨架：
```bash
python -m supervisor.cli inspect
```

#### ② 运行本地离线全链路仿真（验证流水线）
在不打开任何外部软件、不消耗任何 API Token 的情况下，用虚拟数据验证“任务勾选-纠偏-放行”闭环：
```bash
python -m supervisor.cli simulate
```

#### ③ 运行真实监控守护
针对当前打开的 Cursor 窗口进行实机监控：
```bash
python -m supervisor.cli run --driver desktop --window Cursor
```

---

## 配置说明 (`config.yaml`)

```yaml
driver_type: "desktop"          # 驱动模式: desktop | cli | mock
window_title: "Cursor"          # 监控桌面窗口关键字 (如 Cursor / Visual Studio Code)
poll_interval: 2.0              # 轮询探测频率 (秒)
stagnation_timeout: 4.0         # 认定停顿的静默时长阈值 (秒)

tasks_file: "tasks.md"          # 任务检查清单路径
project_root: "."               # 待监控的项目根目录

# 仲裁模型配置 (支持 anthropic / openai / deepseek / mock)
llm_provider: "anthropic"
model_name: "claude-3-5-sonnet-20241022"
# api_key: "sk-..."             # 若不填则自动读取环境变量 ANTHROPIC_API_KEY
max_tokens: 800
temperature: 0.1

# 物理传感器 (零 Token 真实证据链)
run_tests: true
test_command: "pytest -q"
run_lint: true

# 防死锁熔断保护
max_retries_per_task: 3         # 单个任务最多驳回重试次数
similarity_threshold: 0.85      # 文本相似度超 85% 判定为死循环
```
