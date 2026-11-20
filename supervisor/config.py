"""AI Supervisor Watchdog - Configuration Module"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional
import os
import yaml

@dataclass
class WatchdogConfig:
    # Target application settings
    driver_type: str = "desktop"  # "desktop" | "cli" | "mock"
    window_title: str = "Cursor"   # Partial title match for desktop driver
    poll_interval: float = 2.0    # Seconds between UI/process polling
    stagnation_timeout: float = 4.0  # Seconds of silence to consider worker stopped
    
    # Task checklist settings
    tasks_file: str = "tasks.md"
    project_root: str = "."
    
    # LLM Arbiter settings
    llm_provider: str = "anthropic"  # "anthropic" | "openai" | "deepseek" | "gemini" | "mock"
    model_name: str = "claude-3-5-sonnet-20241022"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    max_tokens: int = 1000
    temperature: float = 0.1
    
    # Sensor & Verification settings
    run_tests: bool = True
    test_command: str = "pytest -q"
    run_lint: bool = True
    lint_command: Optional[str] = None
    
    # Circuit Breaker settings
    max_retries_per_task: int = 3
    max_consecutive_failures: int = 5
    similarity_threshold: float = 0.85
    
    @classmethod
    def from_yaml(cls, path: str = "config.yaml") -> "WatchdogConfig":
        config_path = Path(path)
        if not config_path.exists():
            return cls()
        
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            
        # Environment variables override
        api_key = os.getenv("SUPERVISOR_API_KEY") or data.get("api_key")
        if not api_key:
            provider = data.get("llm_provider", "anthropic")
            if provider == "anthropic":
                api_key = os.getenv("ANTHROPIC_API_KEY")
            elif provider in ("openai", "deepseek"):
                api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
            elif provider == "gemini":
                api_key = os.getenv("GEMINI_API_KEY")

        return cls(
            driver_type=data.get("driver_type", "desktop"),
            window_title=data.get("window_title", "Cursor"),
            poll_interval=float(data.get("poll_interval", 2.0)),
            stagnation_timeout=float(data.get("stagnation_timeout", 4.0)),
            tasks_file=data.get("tasks_file", "tasks.md"),
            project_root=data.get("project_root", "."),
            llm_provider=data.get("llm_provider", "anthropic"),
            model_name=data.get("model_name", "claude-3-5-sonnet-20241022"),
            api_key=api_key,
            api_base=data.get("api_base"),
            max_tokens=int(data.get("max_tokens", 1000)),
            temperature=float(data.get("temperature", 0.1)),
            run_tests=bool(data.get("run_tests", True)),
            test_command=data.get("test_command", "pytest -q"),
            lint_command=data.get("lint_command"),
            max_retries_per_task=int(data.get("max_retries_per_task", 3)),
            max_consecutive_failures=int(data.get("max_consecutive_failures", 5)),
            similarity_threshold=float(data.get("similarity_threshold", 0.85)),
        )
