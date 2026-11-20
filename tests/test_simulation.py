import pytest
from pathlib import Path
from supervisor.config import WatchdogConfig
from supervisor.engine import SupervisorEngine
from supervisor.drivers.mock_driver import MockDriver

def test_full_simulation_flow(tmp_path):
    tasks_file = tmp_path / "tasks.md"
    tasks_content = """# Objective: 自动化开发模拟测试
## 执行清单
- [ ] 1. 任务一
- [ ] 2. 任务二
"""
    tasks_file.write_text(tasks_content, encoding="utf-8")

    config = WatchdogConfig(
        driver_type="mock",
        llm_provider="mock",
        tasks_file=str(tasks_file),
        project_root=str(tmp_path),
        run_tests=False,
        run_lint=False
    )

    mock_replies = [
        "任务一顺利实现完毕！",
        "任务二代码已就绪并通过验证！"
    ]
    mock_drv = MockDriver(simulated_responses=mock_replies)

    engine = SupervisorEngine(config=config, driver=mock_drv)
    engine.run()

    # Verify both tasks were marked done in tasks.md
    reloaded_content = tasks_file.read_text(encoding="utf-8")
    assert "- [x] 1. 任务一" in reloaded_content
    assert "- [x] 2. 任务二" in reloaded_content
    assert len(mock_drv.injected_prompts) >= 1
