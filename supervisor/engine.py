"""Main Orchestrator Engine for AI Supervisor Watchdog"""
import time
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from supervisor.config import WatchdogConfig
from supervisor.core.tasks import TaskChecklist
from supervisor.core.repomap import RepoMap
from supervisor.core.linter import CodebaseSensor
from supervisor.core.arbiter import ArbiterEngine, ArbiterDecision
from supervisor.core.circuit_breaker import CircuitBreaker
from supervisor.drivers.base import BaseDriver
from supervisor.drivers.desktop_driver import DesktopDriver
from supervisor.drivers.cli_driver import CLIDriver
from supervisor.drivers.mock_driver import MockDriver

console = Console()

class SupervisorEngine:
    def __init__(self, config: WatchdogConfig, driver: Optional[BaseDriver] = None):
        self.config = config
        self.checklist = TaskChecklist.load(config.tasks_file)
        self.repomap = RepoMap(root_dir=config.project_root)
        self.sensor = CodebaseSensor(
            root_dir=config.project_root,
            test_command=config.test_command if config.run_tests else None,
            lint_command=config.lint_command if config.run_lint else None
        )
        self.arbiter = ArbiterEngine(
            provider=config.llm_provider,
            model_name=config.model_name,
            api_key=config.api_key,
            api_base=config.api_base,
            max_tokens=config.max_tokens,
            temperature=config.temperature
        )
        self.breaker = CircuitBreaker(
            max_retries_per_task=config.max_retries_per_task,
            max_consecutive_failures=config.max_consecutive_failures,
            similarity_threshold=config.similarity_threshold
        )
        self.driver = driver or self._init_driver()

    def _init_driver(self) -> BaseDriver:
        if self.config.driver_type == "desktop":
            return DesktopDriver(window_title=self.config.window_title)
        elif self.config.driver_type == "cli":
            return CLIDriver(command=self.config.window_title, cwd=self.config.project_root)
        else:
            return MockDriver()

    def run(self):
        console.print(Panel(
            f"[bold green]AI Supervisor Watchdog 启动[/bold green]\n"
            f"目标应用: [cyan]{self.config.window_title}[/cyan] ({self.config.driver_type})\n"
            f"任务清单: [yellow]{self.config.tasks_file}[/yellow]\n"
            f"裁决模型: [magenta]{self.config.model_name}[/magenta] (Provider: {self.config.llm_provider})",
            title="Supervisor Status"
        ))

        # Check tasks.md status
        total, completed, remaining = self.checklist.stats
        if remaining == 0:
            console.print("[bold yellow]提示：tasks.md 中所有任务均已标记完成，无需监控。[/bold yellow]")
            return

        console.print(f"[bold cyan]任务总数: {total} | 已完成: {completed} | 待执行: {remaining}[/bold cyan]\n")

        # Connect driver
        if not self.driver.connect():
            console.print("[bold red]错误：无法连接到目标 Worker 进程或窗口，已终止运行。[/bold red]")
            return

        round_num = 1
        try:
            while not self.checklist.is_all_completed:
                current_task = self.checklist.get_current_task()
                if not current_task:
                    break

                console.print(f"\n[bold blue]=== 轮次 {round_num} : 正在监督子任务 #{current_task.index + 1} ===[/bold blue]")
                console.print(f"当前目标: [yellow]{current_task.text}[/yellow]")

                # Step 1: Wait for Worker to stall / pause
                console.print("[dim]等待 Worker AI 停止生成或出现停顿...[/dim]")
                success, worker_last_reply = self.driver.wait_for_stagnation(
                    poll_interval=self.config.poll_interval,
                    timeout=self.config.stagnation_timeout
                )

                if not success:
                    console.print(f"[bold yellow]警告：监听超时或未捕获到停顿: {worker_last_reply}[/bold yellow]")
                    time.sleep(self.config.poll_interval)
                    continue

                console.print(f"[green]捕获到 Worker 停顿输出[/green]: [italic]{worker_last_reply[:120]}...[/italic]")

                # Step 2: Physical Sensor Inspection (0-Token)
                console.print("[dim]正在采集物理代码库事实 (Git Diff & Lint & Tests)...[/dim]")
                sensor_result = self.sensor.inspect()
                sensor_summary = sensor_result.to_summary()

                # Step 3: AST RepoMap Generation (Compact, <1000 tokens)
                repo_skeleton = self.repomap.get_repo_skeleton(focus_files=sensor_result.modified_files)

                # Step 4: Arbiter Evaluation
                console.print("[dim]调用 Supervisor 仲裁模型评估执行结果...[/dim]")
                decision: ArbiterDecision = self.arbiter.evaluate(
                    objective=self.checklist.objective,
                    current_task_text=current_task.text,
                    worker_reply=worker_last_reply,
                    sensor_summary=sensor_summary,
                    repo_skeleton=repo_skeleton
                )

                # Display Decision Panel
                decision_color = "green" if decision.action == "PASS" else ("red" if decision.action == "BLOCKED" else "yellow")
                console.print(Panel(
                    f"[bold {decision_color}]裁决结果: [{decision.action}][/bold {decision_color}]\n"
                    f"原因剖析: {decision.reason}\n"
                    f"下发指令: [italic]{decision.injection_prompt}[/italic]",
                    title=f"Arbiter Decision #{round_num}"
                ))

                # Step 5: Circuit Breaker Inspection
                passed = (decision.action == "PASS")
                can_continue, trip_reason = self.breaker.record_attempt(
                    task_index=current_task.index,
                    passed=passed,
                    prompt_sent=decision.injection_prompt,
                    worker_reply=worker_last_reply
                )

                if not can_continue:
                    console.print(Panel(
                        f"[bold red]熔断器触发，系统已紧急刹车：[/bold red]\n{trip_reason}",
                        title="Circuit Breaker Tripped"
                    ))
                    break

                if decision.action == "BLOCKED":
                    console.print("[bold red]任务遭遇外部阻碍 (BLOCKED)，需要人工介入排查。[/bold red]")
                    break

                # Step 6: State Transition
                if decision.action == "PASS":
                    console.print(f"[bold green]✓ 子任务 #{current_task.index + 1} 验收通过！已自动勾选。[/bold green]")
                    self.checklist.mark_task(current_task.index, "completed", note=decision.reason)
                    next_task = self.checklist.get_current_task()
                    if next_task:
                        next_prompt = f"很好，当前阶段目标已达成。接下来请执行下一个任务：{next_task.text}"
                        self.driver.inject_input(next_prompt)
                    else:
                        console.print("[bold green]🎉 所有清单任务全部圆满完成！[/bold green]")
                        break
                else:
                    # RETRY: Inject feedback prompt into Worker UI/CLI
                    console.print("[bold yellow]⟳ 驳回并下发纠偏指令，驱动 Worker 自愈重试...[/bold yellow]")
                    self.driver.inject_input(decision.injection_prompt)

                round_num += 1
                time.sleep(2.0)

        finally:
            self.driver.close()
            console.print("[dim]Supervisor 已释放所有句柄与监控通道。[/dim]")
