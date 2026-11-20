"""Codebase Sensor & Verification Engine - Inspired by Aider's linter.py and Thoughtworks Sensors"""
import os
import py_compile
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

@dataclass
class SensorResult:
    has_git_changes: bool
    modified_files: List[str]
    git_diff_stat: str
    lint_passed: bool
    lint_output: str
    tests_passed: bool
    test_output: str

    @property
    def is_all_green(self) -> bool:
        return self.lint_passed and self.tests_passed

    def to_summary(self) -> str:
        parts = []
        if self.has_git_changes:
            parts.append(f"【真实代码变动】:\n{self.git_diff_stat}")
        else:
            parts.append("【真实代码变动】: 警告！工作区无任何文件修改（Git Diff 为空）。")

        if not self.lint_passed:
            parts.append(f"【语法/Lint 报错】:\n{self.lint_output}")
        else:
            parts.append("【语法/Lint 状态】: 语法检查通过。")

        if not self.tests_passed:
            parts.append(f"【测试运行状态】: 失败！\n{self.test_output}")
        else:
            parts.append("【测试运行状态】: 全部测试通过。")

        return "\n\n".join(parts)

class CodebaseSensor:
    def __init__(self, root_dir: str = ".", test_command: Optional[str] = None, lint_command: Optional[str] = None):
        self.root_dir = Path(root_dir).resolve()
        self.test_command = test_command
        self.lint_command = lint_command

    def inspect(self) -> SensorResult:
        """Executes all physical sensors and returns structured evidence."""
        has_changes, modified_files, diff_stat = self._check_git()
        lint_passed, lint_out = self._check_lint(modified_files)
        tests_passed, test_out = self._run_tests()

        return SensorResult(
            has_git_changes=has_changes,
            modified_files=modified_files,
            git_diff_stat=diff_stat,
            lint_passed=lint_passed,
            lint_output=lint_out,
            tests_passed=tests_passed,
            test_output=test_out
        )

    def _check_git(self) -> Tuple[bool, List[str], str]:
        """Checks git status and diff."""
        try:
            stat_res = subprocess.run(
                ["git", "status", "--short"],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            raw_stat = stat_res.stdout.strip()
            if not raw_stat:
                return False, [], "No changes."

            # Extract modified file paths
            files = []
            for line in raw_stat.split("\n"):
                parts = line.strip().split(maxsplit=1)
                if len(parts) == 2:
                    files.append(parts[1])

            diff_res = subprocess.run(
                ["git", "diff", "--stat"],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            diff_stat = diff_res.stdout.strip() or raw_stat
            return True, files, diff_stat
        except Exception as e:
            return False, [], f"Git inspection failed: {e}"

    def _check_lint(self, modified_files: List[str]) -> Tuple[bool, str]:
        """Checks syntax using py_compile for Python files, or custom linter."""
        if self.lint_command:
            try:
                res = subprocess.run(
                    self.lint_command,
                    shell=True,
                    cwd=self.root_dir,
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                return res.returncode == 0, (res.stdout + res.stderr).strip()[:1500]
            except Exception as e:
                return False, f"Lint command error: {e}"

        # Default fallback: py_compile for modified Python files
        errors = []
        for file_name in modified_files:
            if file_name.endswith(".py"):
                full_path = self.root_dir / file_name
                if full_path.exists():
                    try:
                        py_compile.compile(str(full_path), doraise=True)
                    except py_compile.PyCompileError as pe:
                        errors.append(f"{file_name}: {pe}")

        if errors:
            return False, "\n".join(errors)
        return True, "Syntax OK."

    def _run_tests(self) -> Tuple[bool, str]:
        """Runs test command if configured."""
        if not self.test_command:
            return True, "Tests skipped (no test command configured)."

        try:
            res = subprocess.run(
                self.test_command,
                shell=True,
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            output = (res.stdout + res.stderr).strip()
            # Truncate to avoid context window explosion
            truncated = output[-1500:] if len(output) > 1500 else output
            return res.returncode == 0, truncated
        except subprocess.TimeoutExpired:
            return False, "Test suite timed out after 30 seconds."
        except Exception as e:
            return False, f"Test execution failed: {e}"
