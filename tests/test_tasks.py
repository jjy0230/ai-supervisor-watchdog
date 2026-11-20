import pytest
from pathlib import Path
from supervisor.core.tasks import TaskChecklist

def test_load_and_parse_tasks(tmp_path):
    md_file = tmp_path / "test_tasks.md"
    content = """# Objective: 测试系统开发
测试总目标描述。

## 待办列表
- [ ] 1. 第一项任务
- [-] 2. 正在执行的任务
- [x] 3. 已完成任务
"""
    md_file.write_text(content, encoding="utf-8")

    checklist = TaskChecklist.load(str(md_file))
    assert "测试系统开发" in checklist.objective
    assert len(checklist.items) == 3
    assert checklist.items[0].status == "pending"
    assert checklist.items[1].status == "in_progress"
    assert checklist.items[2].status == "completed"

    # Verify get_current_task returns first pending/in_progress item
    cur = checklist.get_current_task()
    assert cur is not None
    assert cur.index == 0

    # Mark done
    checklist.mark_task(0, "completed", note="测试通过")
    assert checklist.items[0].status == "completed"

    # Reload from file to ensure persistence
    reloaded = TaskChecklist.load(str(md_file))
    assert reloaded.items[0].status == "completed"
    assert reloaded.get_current_task().index == 1
