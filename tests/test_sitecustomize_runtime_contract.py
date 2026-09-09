import ast
from pathlib import Path


def test_sitecustomize_does_not_monkey_patch_startup_lifecycle():
    source = Path("sitecustomize.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assigned = {
        node.targets[0].attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Attribute)
        and isinstance(node.targets[0].value, ast.Name)
        and node.targets[0].value.id == "_startup"
    }
    assert "run" not in assigned
    assert "post_init" not in source


def test_sitecustomize_preserves_social_dynamic_fanout():
    source = Path("sitecustomize.py").read_text(encoding="utf-8")
    assert "_se._w = _fanout" in source
    assert "get_chat_registry" in source
    assert "application.post_init" not in source
