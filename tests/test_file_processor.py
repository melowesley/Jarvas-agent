import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from jarvas.file_processor import extract_content, process_file, _get_output_dir


def test_extract_txt():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                     delete=False, encoding="utf-8") as f:
        f.write("linha1\nlinha2\n")
        path = f.name
    try:
        content = extract_content(path)
        assert "linha1" in content
        assert "linha2" in content
    finally:
        os.unlink(path)


def test_extract_csv():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv",
                                     delete=False, encoding="utf-8") as f:
        f.write("nome,valor\nAlice,100\nBob,200\n")
        path = f.name
    try:
        content = extract_content(path)
        assert "Alice" in content
        assert "Bob" in content
    finally:
        os.unlink(path)


def test_extract_xlsx():
    import openpyxl
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Nome", "Valor"])
    ws.append(["Alice", 100])
    wb.save(path)
    wb.close()
    try:
        content = extract_content(path)
        assert "Alice" in content
        assert "Nome" in content
    finally:
        try:
            os.unlink(path)
        except PermissionError:
            pass


def test_unsupported_extension():
    content = extract_content("arquivo.xyz")
    assert "[erro]" in content.lower()


def test_output_dir_excel(tmp_path):
    out = _get_output_dir(".xlsx", str(tmp_path))
    assert out.name == "excel"
    assert out.exists()


def test_output_dir_images(tmp_path):
    out = _get_output_dir(".jpg", str(tmp_path))
    assert out.name == "images"


def test_output_dir_no_project():
    out = _get_output_dir(".pdf", None)
    assert out.exists()


@patch("jarvas.file_processor.save_attachment")
@patch("jarvas.hermes_client.chat")
def test_process_file_txt(mock_h, mock_save, tmp_path):
    mock_h.return_value = ("Coluna1\tColuna2\nValor1\tValor2", "model")
    txt = tmp_path / "dados.txt"
    txt.write_text("dados aqui", encoding="utf-8")
    result = process_file(str(txt), "extraia em excel", str(tmp_path), "sess-1")
    assert "output_path" in result
    assert Path(result["output_path"]).exists()


@patch("jarvas.file_processor.save_attachment")
@patch("jarvas.hermes_client.chat")
def test_process_file_saves_to_supabase(mock_h, mock_save, tmp_path):
    mock_h.return_value = ("resultado", "model")
    txt = tmp_path / "nota.txt"
    txt.write_text("conteudo", encoding="utf-8")
    process_file(str(txt), "analise", str(tmp_path), "sess-2")
    mock_save.assert_called_once()
