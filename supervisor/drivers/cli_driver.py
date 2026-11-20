"""Headless CLI Subprocess Driver for Command-Line Agents"""
import os
import subprocess
import threading
import time
from typing import Optional, Tuple
from supervisor.drivers.base import BaseDriver

class CLIDriver(BaseDriver):
    def __init__(self, command: str, cwd: str = "."):
        self.command = command
        self.cwd = cwd
        self.process: Optional[subprocess.Popen] = None
        self.output_buffer = []
        self._reader_thread = None
        self._running = False

    def connect(self) -> bool:
        try:
            self.process = subprocess.Popen(
                self.command,
                shell=True,
                cwd=self.cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            self._running = True
            self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
            self._reader_thread.start()
            return True
        except Exception as e:
            print(f"[CLI Driver] 启动子进程失败: {e}")
            return False

    def _read_output(self):
        while self._running and self.process and self.process.poll() is None:
            line = self.process.stdout.readline()
            if line:
                self.output_buffer.append(line)
                # Print live output with minimal prefix
                print(f"[Worker stdout] {line.strip()}")

    def wait_for_stagnation(self, poll_interval: float = 1.0, timeout: float = 300.0) -> Tuple[bool, str]:
        """
        Detects stagnation when the CLI stops producing output for N seconds
        or terminates.
        """
        start_time = time.time()
        last_len = len(self.output_buffer)
        silence_duration = 0.0

        while time.time() - start_time < timeout:
            if self.process.poll() is not None:
                # Process exited
                recent = "".join(self.output_buffer[-30:])
                return True, recent

            cur_len = len(self.output_buffer)
            if cur_len == last_len:
                silence_duration += poll_interval
                # 3 seconds of silence in CLI typically means it's awaiting input
                if silence_duration >= 3.0 and cur_len > 0:
                    recent = "".join(self.output_buffer[-20:])
                    return True, recent
            else:
                last_len = cur_len
                silence_duration = 0.0

            time.sleep(poll_interval)

        return False, "CLI Driver timed out waiting for output silence."

    def inject_input(self, text: str) -> bool:
        if not self.process or self.process.poll() is not None:
            return False
        try:
            clean_text = text.strip() + "\n"
            self.process.stdin.write(clean_text)
            self.process.stdin.flush()
            return True
        except Exception as e:
            print(f"[CLI Driver] 注入命令失败: {e}")
            return False

    def close(self):
        self._running = False
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass
            self.process = None
