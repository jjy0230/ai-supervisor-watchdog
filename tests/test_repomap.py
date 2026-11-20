from pathlib import Path
from supervisor.core.repomap import RepoMap

def test_python_ast_extraction(tmp_path):
    py_file = tmp_path / "sample.py"
    code = """
class Calculator:
    def add(self, a: int, b: int) -> int:
        \"\"\"Adds two numbers\"\"\"
        return a + b

    async def fetch_data(url: str):
        pass

def standalone_func(x: str) -> bool:
    return len(x) > 0
"""
    py_file.write_text(code, encoding="utf-8")

    repomap = RepoMap(root_dir=str(tmp_path))
    skeleton = repomap.get_repo_skeleton()

    assert "sample.py:" in skeleton
    assert "class Calculator:" in skeleton
    assert "def add(self, a: int, b: int) -> int:" in skeleton
    assert "async def fetch_data(url: str):" in skeleton
    assert "def standalone_func(x: str) -> bool:" in skeleton
