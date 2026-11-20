"""Mock Driver for Automated Testing and Local Simulation"""
from typing import List, Tuple
from supervisor.drivers.base import BaseDriver

class MockDriver(BaseDriver):
    def __init__(self, simulated_responses: List[str] = None):
        self.simulated_responses = simulated_responses or [
            "我已经完成了数据库模型的编写，请检查。",
            "我修复了刚才测试中的类型错误，再次运行测试应该可以通过。",
            "所有接口均已按需求实现完毕！"
        ]
        self.response_idx = 0
        self.injected_prompts: List[str] = []
        self.is_connected = False

    def connect(self) -> bool:
        self.is_connected = True
        return True

    def wait_for_stagnation(self, poll_interval: float = 0.1, timeout: float = 10.0) -> Tuple[bool, str]:
        if self.response_idx < len(self.simulated_responses):
            resp = self.simulated_responses[self.response_idx]
            self.response_idx += 1
            return True, resp
        return True, "当前无新的工作输出。"

    def inject_input(self, text: str) -> bool:
        self.injected_prompts.append(text)
        return True

    def close(self):
        self.is_connected = False
