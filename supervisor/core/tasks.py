"""Tasks & Intent Checklist Engine - Inspired by Roo-Code / Spec-Driven Development"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

@dataclass
class TaskItem:
    index: int
    raw_line: str
    text: str
    status: str  # "pending" | "in_progress" | "completed" | "failed"
    line_number: int

@dataclass
class TaskChecklist:
    objective: str
    items: List[TaskItem] = field(default_factory=list)
    raw_lines: List[str] = field(default_factory=list)
    file_path: Path = Path("tasks.md")

    @classmethod
    def load(cls, file_path: str = "tasks.md") -> "TaskChecklist":
        path = Path(file_path)
        if not path.exists():
            # Return empty or template
            return cls(
                objective="General Development",
                items=[],
                raw_lines=[],
                file_path=path
            )

        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        objective = "Unspecified Goal"
        items: List[TaskItem] = []
        item_counter = 0

        # Regex patterns for markdown checkboxes
        # Matches: - [ ] Task, - [x] Done, - [-] In progress, * [ ] Task, etc.
        checkbox_pattern = re.compile(r"^(\s*[-*]\s*\[\s*([ xX\-!])\s*\]\s*)(.*)")
        header_pattern = re.compile(r"^#+\s*(Objective|目标|Intent|Goal)\s*[:：]?\s*(.*)", re.IGNORECASE)

        in_objective_section = False
        objective_lines = []

        for line_idx, line in enumerate(lines):
            stripped = line.strip()

            # Detect Objective header
            header_match = header_pattern.match(stripped)
            if header_match:
                in_objective_section = True
                direct_obj = header_match.group(2).strip()
                if direct_obj:
                    objective_lines.append(direct_obj)
                continue

            # Detect end of objective section on next header
            if in_objective_section and stripped.startswith("#"):
                in_objective_section = False

            if in_objective_section and stripped:
                objective_lines.append(stripped)

            # Match checkbox item
            cb_match = checkbox_pattern.match(line)
            if cb_match:
                marker = cb_match.group(2)
                text = cb_match.group(3).strip()

                if marker in ("x", "X"):
                    status = "completed"
                elif marker == "-":
                    status = "in_progress"
                elif marker == "!":
                    status = "failed"
                else:
                    status = "pending"

                items.append(TaskItem(
                    index=item_counter,
                    raw_line=line,
                    text=text,
                    status=status,
                    line_number=line_idx
                ))
                item_counter += 1

        if objective_lines:
            objective = "\n".join(objective_lines)

        return cls(
            objective=objective,
            items=items,
            raw_lines=lines,
            file_path=path
        )

    def get_current_task(self) -> Optional[TaskItem]:
        """Returns the first non-completed task."""
        for item in self.items:
            if item.status in ("pending", "in_progress"):
                return item
        return None

    def mark_task(self, item_index: int, new_status: str, note: Optional[str] = None):
        """Updates task state in memory and persists to tasks.md file."""
        target_item = None
        for item in self.items:
            if item.index == item_index:
                target_item = item
                break

        if not target_item:
            return

        marker_map = {
            "completed": "x",
            "in_progress": "-",
            "pending": " ",
            "failed": "!"
        }
        marker = marker_map.get(new_status, " ")
        target_item.status = new_status

        # Update raw line
        line = self.raw_lines[target_item.line_number]
        # Replace the checkbox bracket content
        updated_line = re.sub(r"\[\s*([ xX\-!])\s*\]", f"[{marker}]", line, count=1)
        if note and new_status == "completed":
            updated_line = updated_line.rstrip() + f" <!-- OK: {note} -->\n"
        elif note and new_status == "failed":
            updated_line = updated_line.rstrip() + f" <!-- FAILED: {note} -->\n"

        self.raw_lines[target_item.line_number] = updated_line
        target_item.raw_line = updated_line

        self.save()

    def save(self):
        """Persist current raw lines back to file."""
        with open(self.file_path, "w", encoding="utf-8") as f:
            f.writelines(self.raw_lines)

    @property
    def is_all_completed(self) -> bool:
        if not self.items:
            return True
        return all(item.status == "completed" for item in self.items)

    @property
    def stats(self) -> Tuple[int, int, int]:
        """(total, completed, remaining)"""
        total = len(self.items)
        completed = sum(1 for i in self.items if i.status == "completed")
        remaining = total - completed
        return total, completed, remaining
