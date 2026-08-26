import importlib


def test_v2_modules_import():
    for name in ("core.v2_features", "core.v2_social2", "core.v2_autonomous", "core.vc_player", "core.cricket_v2", "core.deathgames_v2_install"):
        assert importlib.import_module(name)


def test_v2_feature_commands_are_present():
    mod = importlib.import_module("core.v2_features")
    assert hasattr(mod, "cricket")
    assert hasattr(mod, "cricketduel")
    assert hasattr(mod, "oraclepair")
    assert hasattr(mod, "upgradehelp")


def test_vc_player_is_optional_until_configured():
    mod = importlib.import_module("core.vc_player")
    assert hasattr(mod, "player")
    assert hasattr(mod.player, "start")
    assert hasattr(mod.player, "search")


def test_autonomous_layer_is_conservative():
    mod = importlib.import_module("core.v2_autonomous")
    assert mod.QUIET >= 60 * 60
    assert mod.COOLDOWN >= 60 * 60
