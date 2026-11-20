"""Circuit Breaker & Anti-Infinite-Loop Guardrail"""
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

@dataclass
class CircuitBreaker:
    max_retries_per_task: int = 3
    max_consecutive_failures: int = 5
    similarity_threshold: float = 0.85

    # State tracking
    task_retries: Dict[int, int] = field(default_factory=dict)
    consecutive_failures: int = 0
    history_prompts: List[str] = field(default_factory=list)
    history_worker_replies: List[str] = field(default_factory=list)
    is_tripped: bool = False
    trip_reason: Optional[str] = None

    def record_attempt(self, task_index: int, passed: bool, prompt_sent: str, worker_reply: str) -> Tuple[bool, Optional[str]]:
        """
        Records an interaction and checks if safety limits have been violated.
        Returns: (can_continue: bool, trip_reason: Optional[str])
        """
        if self.is_tripped:
            return False, self.trip_reason

        # 1. Similarity / Loop Detection on Worker Output
        if self.history_worker_replies and worker_reply:
            last_reply = self.history_worker_replies[-1]
            # For short strings, require exact match; for longer strings, check ratio
            if len(worker_reply) < 20:
                is_loop = (last_reply.strip() == worker_reply.strip())
                similarity = 1.0 if is_loop else 0.0
            else:
                similarity = SequenceMatcher(None, last_reply.strip(), worker_reply.strip()).ratio()
                is_loop = (similarity > self.similarity_threshold)

            if is_loop and not passed:
                self._trip(f"检测到 Worker 陷入死循环：连续两次回复文本高度相似 ({similarity:.1%}) 且未通过校验。")
                return False, self.trip_reason

        # 2. Similarity / Loop Detection on Supervisor Prompts
        if self.history_prompts and prompt_sent:
            last_prompt = self.history_prompts[-1]
            if len(prompt_sent) < 20:
                is_prompt_loop = (last_prompt.strip() == prompt_sent.strip())
                similarity = 1.0 if is_prompt_loop else 0.0
            else:
                similarity = SequenceMatcher(None, last_prompt.strip(), prompt_sent.strip()).ratio()
                is_prompt_loop = (similarity > self.similarity_threshold)

            if is_prompt_loop and not passed:
                retries = self.task_retries.get(task_index, 0)
                if retries >= 2:
                    self._trip("检测到 Supervisor 发出重复纠偏指令，Worker 无法理解或无有效响应。")
                    return False, self.trip_reason

        self.history_prompts.append(prompt_sent)
        self.history_worker_replies.append(worker_reply)

        if passed:
            self.consecutive_failures = 0
            self.task_retries[task_index] = 0
            return True, None
        else:
            self.consecutive_failures += 1
            retries = self.task_retries.get(task_index, 0) + 1
            self.task_retries[task_index] = retries

            # Check task retry limit
            if retries >= self.max_retries_per_task:
                self._trip(f"当前子任务 (Index {task_index}) 连续重试达 {retries} 次上限，强制暂停交由人工审查。")
                return False, self.trip_reason

            # Check consecutive system failure limit
            if self.consecutive_failures >= self.max_consecutive_failures:
                self._trip(f"系统连续累计失败达 {self.consecutive_failures} 次，触发全局熔断。")
                return False, self.trip_reason

            return True, None

    def _trip(self, reason: str):
        self.is_tripped = True
        self.trip_reason = reason

    def reset(self):
        self.task_retries.clear()
        self.consecutive_failures = 0
        self.history_prompts.clear()
        self.history_worker_replies.clear()
        self.is_tripped = False
        self.trip_reason = None
