from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.character_library import (
    DEFAULT_MANIFEST_PATH,
    CharacterLibrary,
    CrossCharacterPoseError,
    load_manifest,
)


class CharacterLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_manifest(DEFAULT_MANIFEST_PATH)

    def test_manifest_has_20_poses_per_character_and_unique_ids(self) -> None:
        poses = self.manifest["poses"]
        self.assertEqual(40, len(poses))
        self.assertEqual(20, sum(pose["character"] == "yier" for pose in poses))
        self.assertEqual(20, sum(pose["character"] == "bubu" for pose in poses))
        self.assertEqual(40, len({pose["id"] for pose in poses}))
        self.assertEqual(40, len({pose["asset"] for pose in poses}))
        self.assertTrue(all(pose["asset"] == f"{pose['id']}.png" for pose in poses))

    def test_all_40_assets_are_normalized_transparent_pngs(self) -> None:
        for pose in self.manifest["poses"]:
            path = DEFAULT_MANIFEST_PATH.parent / pose["asset"]
            self.assertTrue(path.is_file(), path)
            with Image.open(path) as image:
                self.assertEqual((512, 512), image.size, path)
                self.assertEqual("RGBA", image.mode, path)
                alpha = image.getchannel("A")
                self.assertIsNotNone(alpha.getbbox(), path)
                self.assertEqual(0, alpha.getextrema()[0], path)
                self.assertEqual(255, alpha.getextrema()[1], path)

    def test_explicit_pose_override_wins(self) -> None:
        library = CharacterLibrary(self.manifest, asset_root=DEFAULT_MANIFEST_PATH.parent)
        selected = library.select_pose(
            "female",
            {
                "character_pose": "yier_eyes_sparkle",
                "dialogue_act": "challenge",
                "emotion": "skeptical",
                "interaction_tags": ["disagreement"],
            },
            require_asset=False,
        )
        self.assertEqual("yier_eyes_sparkle", selected["id"])
        self.assertEqual("explicit", selected["selected_by"])
        self.assertFalse(selected["used_fallback"])

    def test_automatic_mapping_uses_speaker_and_turn_semantics(self) -> None:
        library = CharacterLibrary(self.manifest, asset_root=DEFAULT_MANIFEST_PATH.parent)
        selected = library.select_pose(
            "female",
            {
                "dialogue_act": "challenge",
                "emotion": "curious",
                "interaction_tags": ["question"],
            },
            require_asset=False,
        )
        self.assertEqual("yier_curious_tilt", selected["id"])
        self.assertEqual("automatic", selected["selected_by"])

        reverse = library.select_pose(
            "female",
            {
                "dialogue_act": "followup",
                "emotion": "curious",
                "interaction_tags": ["question", "reverse_question"],
            },
            require_asset=False,
        )
        self.assertEqual("yier_reverse_question", reverse["id"])

    def test_cross_character_explicit_pose_is_rejected(self) -> None:
        library = CharacterLibrary(self.manifest, asset_root=DEFAULT_MANIFEST_PATH.parent)
        with self.assertRaises(CrossCharacterPoseError):
            library.select_pose(
                "female",
                {"character_pose": "bubu_gentle_question"},
                require_asset=False,
            )

    def test_missing_image_falls_back_to_character_neutral(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            asset_root = Path(temp_dir)
            # Only the neutral sprite exists.  The requested expressive sprite
            # is intentionally absent.
            (asset_root / "yier_neutral_intro.png").touch()
            library = CharacterLibrary(copy.deepcopy(self.manifest), asset_root=asset_root)
            selected = library.select_pose(
                "female",
                {"character_pose": "yier_happy_solution"},
            )

            self.assertEqual("yier_neutral_intro", selected["id"])
            self.assertEqual("yier_happy_solution", selected["requested_pose_id"])
            self.assertEqual("missing_asset_fallback", selected["selected_by"])
            self.assertTrue(selected["used_fallback"])
            self.assertTrue(selected["asset_available"])


if __name__ == "__main__":
    unittest.main()
