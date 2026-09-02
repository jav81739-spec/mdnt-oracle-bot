from .relationship_media import build_relationship_gif


def test_relationship_media_is_a_real_gif_and_command_specific():
    crossing = build_relationship_gif(
        "These two keep turning up in the same little corners of the group.",
        "crossing",
    )
    fracture = build_relationship_gif(
        "Something changed between them, but it did not finish changing.",
        "fracture",
    )
    assert crossing.read(6) == b"GIF89a"
    assert fracture.read(6) == b"GIF89a"
    assert crossing.getvalue() != fracture.getvalue()


def test_relationship_media_supports_registered_aliases():
    for kind in ("weave", "anchor", "fracture", "ember", "edict", "gaze", "release", "veil"):
        media = build_relationship_gif("A small detail keeps showing up.", kind)
        assert media.read(6) == b"GIF89a"
