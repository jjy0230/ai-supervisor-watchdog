"""LLM Arbiter & Decision Engine - Asymmetric Auditing Layer"""
import json
import re
from dataclasses import dataclass
from typing import Optional
import requests

@dataclass
class ArbiterDecision:
    action: str  # "PASS" | "RETRY" | "BLOCKED"
    injection_prompt: str
    reason: str

class ArbiterEngine:
    def __init__(
        self,
        provider: str = "anthropic",
        model_name: str = "claude-3-5-sonnet-20241022",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        max_tokens: int = 800,
        temperature: float = 0.1
    ):
        self.provider = provider.lower()
        self.model_name = model_name
        self.api_key = api_key
        self.api_base = api_base
        self.max_tokens = max_tokens
        self.temperature = temperature

    def evaluate(
        self,
        objective: str,
        current_task_text: str,
        worker_reply: str,
        sensor_summary: str,
        repo_skeleton: str
    ) -> ArbiterDecision:
        """Evaluates ground truth vs worker claims and renders an unambiguous decision."""
        if self.provider == "mock" or not self.api_key:
            return self._heuristic_evaluate(current_task_text, worker_reply, sensor_summary)

        system_prompt = (
            "你是一个冷酷、严苛的高级技术总监兼代码审计员（Supervisor）。\n"
            "你的任务是核验执行者（Worker AI）是否真正达成了当前子任务目标，并下发下一步指令。\n\n"
            "【审核铁律】:\n"
            "1. 绝不迎合 Worker 的自我吹嘘。如果 Worker 说'完成了'，但物理事实中 Git Diff 为空或测试报错，必须判为 [RETRY] 并严厉指出；\n"
            "2. 如果所有测试通过且改动符合当前子任务，判为 [PASS]，并下发推进到下一任务的指令；\n"
            "3. 如果遇到无法自动解决的外部依赖、缺失凭据或需求冲突，判为 [BLOCKED]；\n"
            "4. 严格按照规定格式输出，不要输出任何多余废话。"
        )

        user_content = f"""
【项目总目标】:
{objective}

【当前正在执行的子任务】:
{current_task_text}

【代码库拓扑骨架 (RepoMap)】:
{repo_skeleton}

【物理传感器事实 (Sensors)】:
{sensor_summary}

【Worker AI 最后一轮回复】:
{worker_reply}

---
请必须严格按照以下格式输出：
[DECISION]: PASS 或 RETRY 或 BLOCKED
[REASON]: <简短具体的裁决原因>
[INJECTION]: <直接注入给 Worker 对话界面的具体指令文本>
"""

        try:
            raw_response = self._call_llm(system_prompt, user_content)
            return self._parse_response(raw_response, current_task_text)
        except Exception as e:
            # Fallback to deterministic heuristic on network/API failure
            return ArbiterDecision(
                action="RETRY",
                injection_prompt=f"外部审计服务异常 ({e})，请继续检查代码规范并确保测试通过。",
                reason=f"LLM API Call Error: {e}"
            )

    def _call_llm(self, system_prompt: str, user_content: str) -> str:
        """Dispatches request to Anthropic or OpenAI-compatible endpoint."""
        if self.provider == "anthropic":
            url = self.api_base or "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            payload = {
                "model": self.model_name,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_content}]
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]

        else:
            # OpenAI / DeepSeek / Ollama compatible
            url = self.api_base or "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model_name,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ]
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    def _parse_response(self, text: str, current_task: str) -> ArbiterDecision:
        dec_match = re.search(r"\[DECISION\]\s*:\s*([A-Za-z]+)", text)
        reason_match = re.search(r"\[REASON\]\s*:\s*(.*?)(?=\n\[INJECTION\]|\Z)", text, re.DOTALL)
        inj_match = re.search(r"\[INJECTION\]\s*:\s*(.*)", text, re.DOTALL)

        action = dec_match.group(1).upper() if dec_match else "RETRY"
        reason = reason_match.group(1).strip() if reason_match else "未解析出明确原因"
        injection = inj_match.group(1).strip() if inj_match else f"请继续推进任务：{current_task}"

        if action not in ("PASS", "RETRY", "BLOCKED"):
            action = "RETRY"

        return ArbiterDecision(
            action=action,
            injection_prompt=injection,
            reason=reason
        )

    def _heuristic_evaluate(self, current_task: str, worker_reply: str, sensor_summary: str) -> ArbiterDecision:
        """Zero-Token heuristic fallback when no LLM API is configured."""
        tests_failed = "测试运行状态】: 失败" in sensor_summary or "语法/Lint 报错" in sensor_summary
        no_changes = "工作区无任何文件修改" in sensor_summary

        if tests_failed:
            return ArbiterDecision(
                action="RETRY",
                injection_prompt="检测到语法报错或单元测试未通过，请根据测试日志修复代码并重新运行测试。",
                reason="Heuristic: 物理测试或语法检查未通过。"
            )
        elif no_changes and ("完成" in worker_reply or "done" in worker_reply.lower()):
            return ArbiterDecision(
                action="RETRY",
                injection_prompt="你声称已完成任务，但当前代码库 Git 状态无任何修改，请提交实际代码变更。",
                reason="Heuristic: Worker 声称完成，但无 Git 变动。"
            )
        else:
            return ArbiterDecision(
                action="PASS",
                injection_prompt=f"当前子任务已验证通过，请继续执行后续规划。",
                reason="Heuristic: 物理传感器全绿，允许放行。"
            )
