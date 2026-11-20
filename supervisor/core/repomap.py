"""Codebase Topology & AST Skeleton Map - Inspired by Aider's repomap.py"""
import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

class RepoMap:
    """
    Extracts a concise Abstract Syntax Tree (AST) skeleton of the repository.
    Enables the Supervisor LLM to understand code structure and calling conventions
    in < 1000 tokens without sending full source files.
    """

    # Files to ignore
    IGNORE_DIRS = {
        ".git", ".svn", "__pycache__", "node_modules", "dist", "build",
        ".venv", "venv", "env", ".idea", ".vscode", "target", ".next"
    }
    ALLOWED_EXTS = {".py", ".ts", ".js", ".jsx", ".tsx", ".go", ".rs", ".java", ".c", ".cpp"}

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()

    def get_repo_skeleton(self, focus_files: Optional[List[str]] = None, max_lines: int = 150) -> str:
        """
        Scans codebase and extracts concise function/class signatures.
        If focus_files is provided, prioritizes them.
        """
        skeleton_blocks = []
        visited_files = self._collect_files()

        # Prioritize focus files if available
        if focus_files:
            focus_paths = [self.root_dir / f for f in focus_files if (self.root_dir / f).exists()]
            non_focus = [f for f in visited_files if f not in focus_paths]
            ordered_files = focus_paths + non_focus
        else:
            ordered_files = visited_files

        total_lines = 0
        for file_path in ordered_files:
            rel_path = file_path.relative_to(self.root_dir)
            ext = file_path.suffix.lower()

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            if ext == ".py":
                sig = self._extract_python_ast(content, str(rel_path))
            else:
                sig = self._extract_generic_signatures(content, str(rel_path), ext)

            if sig:
                block_lines = sig.strip().split("\n")
                if total_lines + len(block_lines) > max_lines:
                    skeleton_blocks.append(f"... (truncated {len(ordered_files) - len(skeleton_blocks)} remaining files)")
                    break
                skeleton_blocks.append(sig)
                total_lines += len(block_lines)

        if not skeleton_blocks:
            return "No source code files detected in repository."

        return "\n\n".join(skeleton_blocks)

    def _collect_files(self) -> List[Path]:
        collected = []
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]
            for file in files:
                p = Path(root) / file
                if p.suffix.lower() in self.ALLOWED_EXTS:
                    collected.append(p)
        return collected

    def _extract_python_ast(self, code: str, rel_path: str) -> Optional[str]:
        """Extracts class and function definitions using standard library ast."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return f"{rel_path}: (Syntax error in parsing)"

        lines = [f"{rel_path}:"]
        has_items = False

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                has_items = True
                base_names = [getattr(b, "id", getattr(b, "attr", "...")) for b in node.bases]
                base_str = f"({', '.join(base_names)})" if base_names else ""
                lines.append(f"  class {node.name}{base_str}:")
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        prefix = "async def" if isinstance(item, ast.AsyncFunctionDef) else "def"
                        args = self._format_args(item.args)
                        ret = f" -> {self._format_ret(item.returns)}" if item.returns else ""
                        lines.append(f"    {prefix} {item.name}({args}){ret}: ...")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                has_items = True
                prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                args = self._format_args(node.args)
                ret = f" -> {self._format_ret(node.returns)}" if node.returns else ""
                lines.append(f"  {prefix} {node.name}({args}){ret}: ...")

        return "\n".join(lines) if has_items else None

    def _format_args(self, args_node: ast.arguments) -> str:
        parts = []
        for a in args_node.args:
            ann = f": {self._format_ret(a.annotation)}" if a.annotation else ""
            parts.append(f"{a.arg}{ann}")
        if args_node.vararg:
            parts.append(f"*{args_node.vararg.arg}")
        if args_node.kwarg:
            parts.append(f"**{args_node.kwarg.arg}")
        return ", ".join(parts)

    def _format_ret(self, node) -> str:
        if node is None:
            return ""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Attribute):
            return f"{self._format_ret(node.value)}.{node.attr}"
        elif isinstance(node, ast.Subscript):
            return f"{self._format_ret(node.value)}[{self._format_ret(node.slice)}]"
        return "..."

    def _extract_generic_signatures(self, code: str, rel_path: str, ext: str) -> Optional[str]:
        """Regex-based fallback for JS/TS/Go/Rust."""
        patterns = [
            # export function / function
            r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\([^)]*\)",
            # class
            r"(?:export\s+)?class\s+([A-Za-z0-9_]+)(?:\s+extends\s+[A-Za-z0-9_]+)?",
            # const fn = () =>
            r"(?:export\s+)?const\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>",
            # Go: func (...) Name(...)
            r"func\s+(?:\([^)]*\)\s+)?([A-Za-z0-9_]+)\s*\([^)]*\)",
            # Rust: pub fn name(...)
            r"(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z0-9_]+)\s*\([^)]*\)",
        ]

        matches = []
        for line in code.split("\n"):
            line_str = line.strip()
            for pat in patterns:
                m = re.match(pat, line_str)
                if m:
                    matches.append(f"  {line_str.split('{')[0].strip()}")
                    break

        if matches:
            return f"{rel_path}:\n" + "\n".join(matches[:15])
        return None
