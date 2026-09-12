def test_python_runtime_is_pinned():
    from pathlib import Path
    assert Path(".python-version").read_text().strip() == "3.11.9"
