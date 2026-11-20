"""Base Driver Interface for Worker AI Interaction"""
from abc import ABC, abstractmethod
from typing import Tuple

class BaseDriver(ABC):
    @abstractmethod
    def connect(self) -> bool:
        """Connects or binds to the target worker environment."""
        pass

    @abstractmethod
    def wait_for_stagnation(self, poll_interval: float = 2.0, timeout: float = 300.0) -> Tuple[bool, str]:
        """
        Blocks until the worker AI stops generating or pauses waiting for input.
        Returns: (success: bool, last_worker_message: str)
        """
        pass

    @abstractmethod
    def inject_input(self, text: str) -> bool:
        """Injects text into the worker chat/CLI and triggers execution."""
        pass

    @abstractmethod
    def close(self):
        """Clean up resources."""
        pass
