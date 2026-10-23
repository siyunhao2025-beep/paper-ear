#!/usr/bin/env python3
"""Load, validate, and select Paper Ear's Bubu/Yier character poses.

The manifest contains creative fan-made presentation cues.  It does not make
any claim that the actions, captions, images, or voices are official IP assets.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Optional, Sequence, Union


DEFAULT_MANIFEST_PATH = (
    Path(__file__).resolve().parents[1] / "assets" / "characters" / "manifest.json"
)

CHARACTERS = {"yier", "bubu"}
SPEAKER_TO_CHARACTER = {"female": "yier", "male": "bubu"}
DIALOGUE_ACTS = {
    "claim",
    "challenge",
    "evidence_answer",
    "followup",
    "concession",
    "synthesis",
}
EMOTIONS = {
    "neutral",
    "curious",
    "skeptical",
    "serious",
    "surprised",
    "excited",
    "reflective",
}
INTERACTION_TAGS = {
    "question",
    "disagreement",
    "surprise",
    "concession",
    "self_correction",
    "reverse_question",
    "unresolved",
}
REQUIRED_POSE_FIELDS = {
    "id",
    "character",
    "emotion_zh",
    "action_zh",
    "caption_zh",
    "asset",
    "triggers",
}

# A specific conversational event should outrank a generic question when both
# match the same turn.  These weights make the choice deterministic without
# encoding any paper-specific wording in the renderer.
TAG_WEIGHTS = {
    "self_correction": 13,
    "reverse_question": 12,
    "unresolved": 10,
    "disagreement": 9,
    "concession": 8,
    "surprise": 7,
    "question": 5,
}


class CharacterLibraryError(ValueError):
    """Base error for malformed manifests or invalid pose requests."""


class UnknownPoseError(CharacterLibraryError):
    """Raised when ``turn.character_pose`` does not name a known pose."""


class CrossCharacterPoseError(CharacterLibraryError):
    """Raised when a speaker explicitly requests the other character's pose."""


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_trigger_list(
    pose_id: str,
    triggers: Mapping[str, Any],
    field: str,
    allowed: set[str],
    errors: list[str],
) -> None:
    values = triggers.get(field)
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        errors.append(f"{pose_id}: triggers.{field} must be a string array")
        return
    if len(values) != len(set(values)):
        errors.append(f"{pose_id}: triggers.{field} contains duplicate values")
    unknown = sorted(set(values) - allowed)
    if unknown:
        errors.append(f"{pose_id}: triggers.{field} contains unsupported values {unknown}")


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    """Validate the fixed 20+20 Bubu/Yier pose contract.

    Asset existence is deliberately not checked here: generated image files may
    be installed after the metadata.  :class:`CharacterLibrary` performs that
    runtime check and falls back to the character's neutral pose.
    """

    errors: list[str] = []
    if not isinstance(manifest, Mapping):
        raise CharacterLibraryError("character manifest must be a JSON object")

    speaker_map = manifest.get("speaker_map")
    if speaker_map != SPEAKER_TO_CHARACTER:
        errors.append(f"speaker_map must equal {SPEAKER_TO_CHARACTER}")

    neutral_pose = manifest.get("neutral_pose")
    if not isinstance(neutral_pose, Mapping) or set(neutral_pose) != CHARACTERS:
        errors.append("neutral_pose must map exactly yier and bubu")

    poses = manifest.get("poses")
    if not isinstance(poses, list):
        errors.append("poses must be an array")
        poses = []

    ids: list[str] = []
    assets: list[str] = []
    per_character = {character: 0 for character in CHARACTERS}

    for index, pose in enumerate(poses):
        where = f"poses[{index}]"
        if not isinstance(pose, Mapping):
            errors.append(f"{where} must be an object")
            continue

        missing = sorted(REQUIRED_POSE_FIELDS - set(pose))
        if missing:
            errors.append(f"{where} is missing fields {missing}")

        pose_id = pose.get("id")
        character = pose.get("character")
        if not _nonempty_text(pose_id):
            errors.append(f"{where}.id must be non-empty text")
            pose_id = where
        else:
            ids.append(pose_id)
        if character not in CHARACTERS:
            errors.append(f"{pose_id}: character must be one of {sorted(CHARACTERS)}")
        else:
            per_character[character] += 1
            if isinstance(pose_id, str) and not pose_id.startswith(f"{character}_"):
                errors.append(f"{pose_id}: id must start with '{character}_'")

        for field in ("emotion_zh", "action_zh", "caption_zh"):
            if not _nonempty_text(pose.get(field)):
                errors.append(f"{pose_id}: {field} must be non-empty text")

        asset = pose.get("asset")
        if not _nonempty_text(asset):
            errors.append(f"{pose_id}: asset must be a non-empty relative PNG path")
        else:
            assets.append(asset)
            asset_path = PurePosixPath(asset)
            if asset_path.is_absolute() or ".." in asset_path.parts or asset_path.suffix.lower() != ".png":
                errors.append(f"{pose_id}: asset must be a safe relative .png path")

        triggers = pose.get("triggers")
        if not isinstance(triggers, Mapping):
            errors.append(f"{pose_id}: triggers must be an object")
        else:
            if set(triggers) != {"dialogue_act", "emotion", "tags"}:
                errors.append(
                    f"{pose_id}: triggers must contain exactly dialogue_act, emotion, and tags"
                )
            _validate_trigger_list(pose_id, triggers, "dialogue_act", DIALOGUE_ACTS, errors)
            _validate_trigger_list(pose_id, triggers, "emotion", EMOTIONS, errors)
            _validate_trigger_list(pose_id, triggers, "tags", INTERACTION_TAGS, errors)

    if len(poses) != 40:
        errors.append(f"manifest must contain exactly 40 poses; found {len(poses)}")
    for character, count in sorted(per_character.items()):
        if count != 20:
            errors.append(f"{character} must contain exactly 20 poses; found {count}")
    if len(ids) != len(set(ids)):
        errors.append("pose ids must be globally unique")
    if len(assets) != len(set(assets)):
        errors.append("pose asset paths must be globally unique")

    id_to_character = {
        pose.get("id"): pose.get("character")
        for pose in poses
        if isinstance(pose, Mapping)
    }
    if isinstance(neutral_pose, Mapping):
        for character in sorted(CHARACTERS):
            pose_id = neutral_pose.get(character)
            if pose_id not in id_to_character:
                errors.append(f"neutral_pose.{character} references unknown pose '{pose_id}'")
            elif id_to_character[pose_id] != character:
                errors.append(f"neutral_pose.{character} references the wrong character")

    if errors:
        raise CharacterLibraryError("Invalid character manifest:\n- " + "\n- ".join(errors))


def load_manifest(path: Union[str, Path] = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    """Read a UTF-8 manifest and validate its metadata contract."""

    manifest_path = Path(path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CharacterLibraryError(f"character manifest not found: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise CharacterLibraryError(f"invalid character manifest JSON: {exc}") from exc
    validate_manifest(manifest)
    return manifest


def character_for_speaker(speaker: str) -> str:
    """Map dialogue speakers to the fixed cast (female=Yier, male=Bubu)."""

    normalized = str(speaker).strip().lower()
    try:
        return SPEAKER_TO_CHARACTER[normalized]
    except KeyError as exc:
        raise CharacterLibraryError("speaker must be 'female' or 'male'") from exc


class CharacterLibrary:
    """Validated pose metadata plus deterministic per-turn pose selection."""

    def __init__(
        self,
        manifest: Mapping[str, Any],
        *,
        asset_root: Union[str, Path],
    ) -> None:
        validate_manifest(manifest)
        self.manifest = copy.deepcopy(dict(manifest))
        self.asset_root = Path(asset_root).resolve()
        self._poses = list(self.manifest["poses"])
        self._pose_by_id = {pose["id"]: pose for pose in self._poses}

    @classmethod
    def from_file(
        cls,
        manifest_path: Union[str, Path] = DEFAULT_MANIFEST_PATH,
        *,
        asset_root: Optional[Union[str, Path]] = None,
    ) -> "CharacterLibrary":
        path = Path(manifest_path)
        return cls(load_manifest(path), asset_root=asset_root or path.parent)

    def get_pose(self, pose_id: str) -> dict[str, Any]:
        """Return a copy of a pose or raise :class:`UnknownPoseError`."""

        try:
            return copy.deepcopy(self._pose_by_id[pose_id])
        except KeyError as exc:
            raise UnknownPoseError(f"unknown character pose '{pose_id}'") from exc

    def asset_path(self, pose: Union[Mapping[str, Any], str]) -> Path:
        """Return the absolute path for a validated pose asset."""

        pose_data = self._pose_by_id[pose] if isinstance(pose, str) else pose
        return (self.asset_root / PurePosixPath(pose_data["asset"])).resolve()

    @staticmethod
    def _turn_tags(turn: Mapping[str, Any]) -> set[str]:
        value = turn.get("interaction_tags", turn.get("tags", []))
        if isinstance(value, str):
            return {value.lower()}
        if not isinstance(value, Sequence):
            return set()
        return {str(tag).lower() for tag in value}

    def _automatic_pose(self, character: str, turn: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
        dialogue_act = str(turn.get("dialogue_act", "")).lower()
        emotion = str(turn.get("emotion", "")).lower()
        turn_tags = self._turn_tags(turn)

        best_pose: Optional[dict[str, Any]] = None
        best_rank: Optional[tuple[int, int, int, int]] = None
        for index, pose in enumerate(self._poses):
            if pose["character"] != character:
                continue
            triggers = pose["triggers"]
            act_match = int(bool(dialogue_act and dialogue_act in triggers["dialogue_act"]))
            emotion_match = int(bool(emotion and emotion in triggers["emotion"]))
            matched_tags = turn_tags.intersection(triggers["tags"])
            missing_tags = set(triggers["tags"]) - turn_tags
            tag_score = sum(TAG_WEIGHTS.get(tag, 1) for tag in matched_tags)
            score = tag_score + 4 * act_match + 3 * emotion_match - 2 * len(missing_tags)
            match_count = act_match + emotion_match + len(matched_tags)
            # Earlier manifest entries win a genuinely identical tie.
            rank = (score, tag_score, match_count, -index)
            if score > 0 and (best_rank is None or rank > best_rank):
                best_pose = pose
                best_rank = rank

        if best_pose is None:
            neutral_id = self.manifest["neutral_pose"][character]
            return self._pose_by_id[neutral_id], "neutral_no_trigger"
        return best_pose, "automatic"

    def _runtime_result(
        self,
        pose: Mapping[str, Any],
        *,
        selected_by: str,
        used_fallback: bool,
        requested_pose_id: str,
    ) -> dict[str, Any]:
        result = copy.deepcopy(dict(pose))
        path = self.asset_path(pose)
        result.update(
            {
                "asset_path": str(path),
                "asset_available": path.is_file(),
                "selected_by": selected_by,
                "used_fallback": used_fallback,
                "requested_pose_id": requested_pose_id,
            }
        )
        return result

    def select_pose(
        self,
        speaker: str,
        turn: Mapping[str, Any],
        *,
        require_asset: bool = True,
    ) -> dict[str, Any]:
        """Select a pose using an explicit override or semantic triggers.

        ``turn.character_pose`` always wins.  A pose belonging to the other
        character is rejected instead of silently changing the cast.  When the
        requested/automatic image is missing and ``require_asset`` is true, the
        character's neutral pose metadata is returned.  If even that neutral
        PNG is absent, callers still receive a safe neutral record with
        ``asset_available=false`` and may render no sprite.
        """

        if not isinstance(turn, Mapping):
            raise CharacterLibraryError("turn must be an object")
        character = character_for_speaker(speaker)
        explicit = turn.get("character_pose")

        if explicit is not None:
            if not _nonempty_text(explicit):
                raise UnknownPoseError("character_pose must be a non-empty pose id")
            pose = self._pose_by_id.get(explicit)
            if pose is None:
                raise UnknownPoseError(f"unknown character pose '{explicit}'")
            if pose["character"] != character:
                raise CrossCharacterPoseError(
                    f"speaker '{speaker}' maps to {character} and cannot use '{explicit}'"
                )
            selected_by = "explicit"
        else:
            pose, selected_by = self._automatic_pose(character, turn)

        requested_pose_id = pose["id"]
        if require_asset and not self.asset_path(pose).is_file():
            neutral_id = self.manifest["neutral_pose"][character]
            neutral_pose = self._pose_by_id[neutral_id]
            if pose["id"] != neutral_id:
                return self._runtime_result(
                    neutral_pose,
                    selected_by="missing_asset_fallback",
                    used_fallback=True,
                    requested_pose_id=requested_pose_id,
                )

        return self._runtime_result(
            pose,
            selected_by=selected_by,
            used_fallback=False,
            requested_pose_id=requested_pose_id,
        )


def select_pose(
    speaker: str,
    turn: Mapping[str, Any],
    *,
    manifest_path: Union[str, Path] = DEFAULT_MANIFEST_PATH,
    asset_root: Optional[Union[str, Path]] = None,
    require_asset: bool = True,
) -> dict[str, Any]:
    """One-call convenience wrapper around :class:`CharacterLibrary`."""

    library = CharacterLibrary.from_file(manifest_path, asset_root=asset_root)
    return library.select_pose(speaker, turn, require_asset=require_asset)


__all__ = [
    "CHARACTERS",
    "DEFAULT_MANIFEST_PATH",
    "SPEAKER_TO_CHARACTER",
    "CharacterLibrary",
    "CharacterLibraryError",
    "CrossCharacterPoseError",
    "UnknownPoseError",
    "character_for_speaker",
    "load_manifest",
    "select_pose",
    "validate_manifest",
]
