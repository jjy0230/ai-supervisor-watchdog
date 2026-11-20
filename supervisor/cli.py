"""Command-Line Interface for AI Supervisor Watchdog"""
import argparse
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table

from supervisor.config import WatchdogConfig
from supervisor.engine import SupervisorEngine
from supervisor.core.tasks import TaskChecklist
from supervisor.core.repomap import RepoMap
from supervisor.core.linter import CodebaseSensor
from supervisor.drivers.mock_driver import MockDriver

console = Console()

def cmd_init(args):
    """Initializes sample tasks.md and config.yaml in target folder."""
    tasks_content = """# Objective: 示例项目自动化开发
本项目旨在构建一个高内聚、易测试的用户认证服务。

## 任务执行清单
- [ ] 1. 编写用户数据模型 `User` (包含 username, email, password_hash)
- [ ] 2. 编写密码加密与验证工具函数
- [ ] 3. 编写注册与登录逻辑单元测试
- [ ] 4. 运行并通过全部单元测试
"""
    config_content = """# AI Supervisor Watchdog 配置
driver_type: "desktop"          # 驱动模式: "desktop" (Cursor/VS Code) | "cli" (命令行Agent) | "mock" (仿真模拟)
window_title: "Cursor"          # 监听目标窗口标题关键字
poll_interval: 2.0              # 轮询探测间隔 (秒)
stagnation_timeout: 4.0         # 认定停顿的静默时长阈值 (秒)

tasks_file: "tasks.md"          # 任务检查清单路径
project_root: "."               # 待监控的项目根目录

# 仲裁模型配置 (支持 anthropic / openai / deepseek / gemini / mock)
llm_provider: "anthropic"
model_name: "claude-3-5-sonnet-20241022"
# api_key: "sk-..."             # 若未填写则自动读取环境变量 ANTHROPIC_API_KEY
max_tokens: 800
temperature: 0.1

# 物理传感器配置
run_tests: true
test_command: "pytest -q"
run_lint: true

# 防死锁熔断保护
max_retries_per_task: 3
max_consecutive_failures: 5
"""
    t_path = Path("tasks.md")
    c_path = Path("config.yaml")

    if not t_path.exists():
        t_path.write_text(tasks_content, encoding="utf-8")
        console.print("[green]已生成初始任务清单: tasks.md[/green]")
    else:
        console.print("[yellow]tasks.md 已存在，跳过。[/yellow]")

    if not c_path.exists():
        c_path.write_text(config_content, encoding="utf-8")
        console.print("[green]已生成初始配置文件: config.yaml[/green]")
    else:
        console.print("[yellow]config.yaml 已存在，跳过。[/yellow]")

def cmd_inspect(args):
    """Inspects codebase AST skeleton and physical sensor output without invoking LLM."""
    config = WatchdogConfig.from_yaml(args.config)
    checklist = TaskChecklist.load(config.tasks_file)
    repomap = RepoMap(root_dir=config.project_root)
    sensor = CodebaseSensor(
        root_dir=config.project_root,
        test_command=config.test_command if config.run_tests else None,
        lint_command=config.lint_command if config.run_lint else None
    )

    console.rule("[bold cyan]1. 任务清单状态 (Tasks Status)[/bold cyan]")
    total, completed, remaining = checklist.stats
    table = Table(title=f"目标: {checklist.objective}")
    table.add_column("序号", justify="center")
    table.add_column("状态", justify="center")
    table.add_column("任务描述")
    for item in checklist.items:
        status_color = "green" if item.status == "completed" else "yellow"
        table.add_row(str(item.index + 1), f"[{status_color}]{item.status}[/{status_color}]", item.text)
    console.print(table)
    console.print(f"总计: {total} | 已完成: {completed} | 待执行: {remaining}\n")

    console.rule("[bold cyan]2. 物理传感器检测结果 (Sensors)[/bold cyan]")
    res = sensor.inspect()
    console.print(res.to_summary())
    console.print()

    console.rule("[bold cyan]3. 代码库 AST 拓扑骨架 (RepoMap 预览)[/bold cyan]")
    skeleton = repomap.get_repo_skeleton(focus_files=res.modified_files, max_lines=40)
    console.print(skeleton)

def cmd_simulate(args):
    """Runs an offline simulation with MockDriver to verify pipeline logic without third-party apps."""
    config = WatchdogConfig.from_yaml(args.config)
    config.driver_type = "mock"
    config.llm_provider = "mock"  # Pure zero-token heuristic mode
    config.run_tests = False      # Bypass external test execution during mock
    
    simulated_replies = [
        "我已经完成了用户模型的建立，代码已就绪。",
        "修复了刚才的测试错误。",
        "全部任务已交付。"
    ]
    mock_drv = MockDriver(simulated_responses=simulated_replies)
    engine = SupervisorEngine(config=config, driver=mock_drv)
    engine.run()

def cmd_run(args):
    """Starts live watchdog supervisor."""
    config = WatchdogConfig.from_yaml(args.config)
    if args.driver:
        config.driver_type = args.driver
    if args.window:
        config.window_title = args.window
    
    engine = SupervisorEngine(config=config)
    engine.run()

def main():
    parser = argparse.ArgumentParser(description="AI Supervisor Watchdog CLI")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    subparsers = parser.add_subparsers(dest="subcommand")

    # init
    subparsers.add_parser("init", help="Initialize sample tasks.md and config.yaml")

    # inspect
    subparsers.add_parser("inspect", help="Inspect codebase topology and sensor readings")

    # simulate
    subparsers.add_parser("simulate", help="Run local deterministic simulation with MockDriver")

    # run
    run_parser = subparsers.add_parser("run", help="Start the supervisor watchdog")
    run_parser.add_argument("--driver", choices=["desktop", "cli", "mock"], help="Override driver type")
    run_parser.add_argument("--window", help="Override window title search string")

    args = parser.parse_args()

    if args.subcommand == "init":
        cmd_init(args)
    elif args.subcommand == "inspect":
        cmd_inspect(args)
    elif args.subcommand == "simulate":
        cmd_simulate(args)
    elif args.subcommand == "run" or args.subcommand is None:
        cmd_run(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
