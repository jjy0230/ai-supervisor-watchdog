"""Desktop UI Automation Driver - Windows Native UIA 3.0 via uiautomation"""
import time
from typing import Optional, Tuple
from supervisor.drivers.base import BaseDriver

try:
    import uiautomation as auto
    HAS_UIA = True
except ImportError:
    HAS_UIA = False

class DesktopDriver(BaseDriver):
    def __init__(self, window_title: str = "Cursor"):
        self.window_title = window_title
        self.target_window = None

    def connect(self) -> bool:
        if not HAS_UIA:
            print("[错误] 未安装 uiautomation 库，无法启用 DesktopDriver。")
            return False

        # Search for window matching partial title
        self.target_window = auto.WindowControl(searchDepth=2, SubName=self.window_title)
        if not self.target_window.Exists(maxSearchSeconds=3):
            print(f"[警告] 未找到标题包含 '{self.window_title}' 的桌面窗口。")
            return False

        print(f"[连接成功] 已捕获目标窗口: {self.target_window.Name}")
        return True

    def wait_for_stagnation(self, poll_interval: float = 2.0, timeout: float = 300.0) -> Tuple[bool, str]:
        """
        Polls the desktop UI until the generation stops.
        Detection heuristics:
        1. 'Stop Generating' button is NOT visible.
        2. Input field is enabled.
        3. Reads last message bubble text.
        """
        if not self.target_window:
            if not self.connect():
                return False, "Target window disconnected."

        start_time = time.time()
        last_extracted_text = ""
        stable_count = 0

        while time.time() - start_time < timeout:
            if not self.target_window.Exists(0, 0):
                return False, "Target window closed during monitoring."

            # Check for 'Stop' / 'Cancel' generation buttons
            stop_btn = self.target_window.ButtonControl(searchDepth=10, SubName="Stop")
            is_generating = stop_btn.Exists(0, 0) and stop_btn.IsEnabled

            if not is_generating:
                # Generation has ceased, extract last text
                current_text = self._extract_latest_message()
                if current_text:
                    if current_text == last_extracted_text:
                        stable_count += 1
                        # If text has been stable for 2 polling intervals (~4 seconds), confirm stagnation
                        if stable_count >= 2:
                            return True, current_text
                    else:
                        last_extracted_text = current_text
                        stable_count = 0

            time.sleep(poll_interval)

        return False, "Timed out waiting for worker AI stagnation."

    def inject_input(self, text: str) -> bool:
        """Injects text into the chat input box and triggers submission."""
        if not self.target_window:
            if not self.connect():
                return False

        try:
            # Locate input box: typically EditControl or DocumentControl inside chat pane
            edit_control = self.target_window.EditControl(searchDepth=12)
            if not edit_control.Exists(1, 0):
                # Fallback to DocumentControl
                edit_control = self.target_window.DocumentControl(searchDepth=12)

            if not edit_control.Exists(1, 0):
                print("[错误] 未能定位到聊天输入框控件。")
                return False

            # Focus and inject text via ValuePattern to avoid mouse displacement
            edit_control.SetFocus()
            val_pattern = edit_control.GetValuePattern()
            if val_pattern:
                val_pattern.SetValue(text)
            else:
                edit_control.SendKeys(text)

            time.sleep(0.5)

            # Locate submit button or send Enter
            send_btn = self.target_window.ButtonControl(searchDepth=12, SubName="Send")
            if send_btn.Exists(1, 0) and send_btn.IsEnabled:
                send_btn.Click(simulateMove=False)
            else:
                # Fallback to Enter key
                edit_control.SendKeys("{Enter}")

            return True
        except Exception as e:
            print(f"[注入异常] {e}")
            return False

    def _extract_latest_message(self) -> str:
        """Extracts text content from the latest chat response bubble."""
        try:
            # Traverses chat document or list controls
            chat_pane = self.target_window.DocumentControl(searchDepth=8)
            if not chat_pane.Exists(0, 0):
                chat_pane = self.target_window.ListControl(searchDepth=8)

            if chat_pane.Exists(0, 0):
                children = chat_pane.GetChildren()
                if children:
                    # Return the name/text of the last child node
                    last_child = children[-1]
                    return last_child.Name or ""
        except Exception:
            pass
        return "Worker output detected (text parsing fallback)."

    def close(self):
        self.target_window = None
