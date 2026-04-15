import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from jarvas.file_editor import read_file, edit_file


def test_read_file_absolute():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                     delete=False, encoding="utf-8") as f:
        f.write("def hello(): pass\n")
        path = f.name
    try:
        content = read_file(path)
        assert "def hello" in content
    finally:
        os.unlink(path)


def test_read_file_relative_with_project_base():
    with tempfile.TemporaryDirectory() as tmpdir:
        fpath = Path(tmpdir) / "main.py"
        fpath.write_text("x = 1\n", encoding="utf-8")
        content = read_file("main.py", project_base=tmpdir)
        assert "x = 1" in content


def test_read_file_not_found():
    result = read_file("/caminho/inexistente/arquivo.py")
    assert "[erro]" in result.lower()


def test_read_file_blocks_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"
        env_path.write_text("SECRET=123\n", encoding="utf-8")
        result = read_file(str(env_path))
        assert "[erro]" in result.lower()


def test_read_file_blocks_pem():
    with tempfile.TemporaryDirectory() as tmpdir:
        pem_path = Path(tmpdir) / "cert.pem"
        pem_path.write_text("-----BEGIN CERTIFICATE-----\n", encoding="utf-8")
        result = read_file(str(pem_path))
        assert "[erro]" in result.lower()


@patch("jarvas.file_editor.save_file_edit")
@patch("jarvas.file_editor.run_edit")
def test_edit_file_writes_to_disk(mock_run_edit, mock_save):
    mock_run_edit.return_value = "def hello():\n    \"\"\"Oi.\"\"\"\n    pass\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                     delete=False, encoding="utf-8") as f:
        f.write("def hello(): pass\n")
        path = f.name
    try:
        result = edit_file(path, "adicione docstring", None, "sess-001")
        assert "diff" in result
        assert Path(path).read_text(encoding="utf-8") == mock_run_edit.return_value
    finally:
        os.unlink(path)


@patch("jarvas.file_editor.save_file_edit")
@patch("jarvas.file_editor.run_edit")
def test_edit_file_blocks_env(mock_run_edit, mock_save):
    with tempfile.TemporaryDirectory() as tmpdir:
        env = Path(tmpdir) / ".env"
        env.write_text("X=1\n", encoding="utf-8")
        result = edit_file(str(env), "edite", None, "sess-001")
        assert "error" in result
        mock_run_edit.assert_not_called()
