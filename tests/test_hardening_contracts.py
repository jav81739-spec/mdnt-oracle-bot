import unittest


class HardeningContractTests(unittest.TestCase):
    def test_compatibility_surfaces_import(self):
        from handlers import economy_compat, deathgames_hardened

        for callback in (
            economy_compat.checkin_command,
            economy_compat.cgift_command,
            economy_compat.coinboard_command,
            economy_compat.rob_command,
            deathgames_hardened.survive,
            deathgames_hardened.revive,
        ):
            self.assertTrue(callable(callback))

    def test_economy_exposes_idempotent_mutations(self):
        from core.economy import service

        self.assertTrue(callable(service.add_once))
        self.assertTrue(callable(service.remove_once))

    def test_legacy_surface_declares_single_owners(self):
        from handlers.legacy_surface import _assert_no_duplicate_declarations

        _assert_no_duplicate_declarations(
            {"a": {"alpha": "x"}, "b": {"beta": "y"}},
            {"gamma": "z"},
        )
        with self.assertRaises(RuntimeError):
            _assert_no_duplicate_declarations(
                {"a": {"alpha": "x"}, "b": {"alpha": "y"}},
                {},
            )


if __name__ == "__main__":
    unittest.main()
