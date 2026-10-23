# Bubu/Yier local F5-TTS backend

Snapshot date: 2026-10-23.

`bubu-yier-local` is an optional, on-device Paper-Ear voice backend. It uses
F5-TTS zero-shot synthesis with the two reference clips published by
[BoxAudio-0](https://github.com/Boxjod/box2audio-0). Paper-Ear does not vendor
the clips, model weights, account credentials, PDFs, or extracted paper text.

## Fixed cast profile

The `bubu-yier-v1` brand profile uses:

| Paper-Ear role | Character voice | Configuration value |
|---|---|---|
| female presenter | 一二 | `yier` |
| male discussant | 布布 | `bubu` |

The backend accepts any individual turn, including renderer-injected opening
turns. It does not hard-code opening copy. `synthesize_turn_audio` selects only
that turn's final `spoken_text` (falling back to `zh_text`/`en_text` under the
normal renderer contract), and the F5-TTS adapter receives only the selected
string plus local voice controls. It has no access to the PDF, evidence map,
page images, subtitles, citations, or run directory.

## Install and verify

This themed voice backend requires **Python 3.10 or newer**. The setup script
checks the interpreter version before touching the external voice cache and
prints an actionable error on older runtimes.

Install the optional Python engine:

```powershell
python -m pip install -r requirements-bubu-yier.txt
```

Install the two reference clips into the external user cache and verify them:

```powershell
python scripts/setup_bubu_yier_voice.py
python scripts/setup_bubu_yier_voice.py --check-only
```

The default cache is `~/.cache/paper-ear/bubu-yier-f5`. Override it with
`PAPER_EAR_BUBU_YIER_DIR` or a profile-level `reference_dir`. The installer
pins BoxAudio-0 commit `66baffbdd5ba6e2f12efa4067778d420a9f422a7` and
rejects either clip when its SHA-256 digest differs:

| Voice | File | SHA-256 |
|---|---|---|
| 一二 | `yier_self_introduction.wav` | `190f80be27f1774a29e5443b6db3dfa0961e2e1ec72c4b5e951c042926dbad7b` |
| 布布 | `bubu_self_introduction.wav` | `47ba63de2a8efeb84d901c684c7fcf525d2b11f8af209916609f3c89caef3431` |

For an offline install from an already checked-out BoxAudio-0 repository, pass
its `assets/audio` directory with `--source-dir`. The same hashes are enforced.

## Voice-casting configuration

```json
{
  "brand_profile": "bubu-yier-v1",
  "voice_backend": "bubu-yier-local",
  "voice_model": "F5TTS_v1_Base",
  "female_voice": "yier",
  "male_voice": "bubu",
  "voice_profiles": {
    "female": {
      "model": "F5TTS_v1_Base",
      "voice": "yier",
      "rate": "+0%",
      "pitch": "+0Hz",
      "volume": "+0%",
      "trim_silence": true,
      "seed": 42
    },
    "male": {
      "model": "F5TTS_v1_Base",
      "voice": "bubu",
      "rate": "+0%",
      "pitch": "+0Hz",
      "volume": "+0%",
      "trim_silence": true,
      "seed": 42
    }
  }
}
```

When `voice_profiles` or the legacy voice fields omit a voice,
`bubu-yier-local` defaults female to `yier` and male to `bubu`. Under
`brand_profile: bubu-yier-v1`, the renderer rejects any root-level or
profile-level attempt to change female away from `yier`, male away from
`bubu`, or the model away from `F5TTS_v1_Base`. Branded display names must
start with `一二` and `布布`, respectively; role suffixes remain allowed.

Under `brand_profile: bubu-yier-v1`, each role must match the pinned reference
SHA-256 and transcript in the table above. An explicit `reference_audio` path
is accepted only when the file is byte-identical to that pinned recording;
providing the checksum of a different WAV does not make it a branded reference.
Use a separate, non-branded profile for an authorized replacement recording,
and require a fresh listening decision for that profile.

The final `spoken_text` also carries the role-addressing contract: 布布
(`male`) may address 一二 as `一二宝`; 一二 (`female`) may address 布布 as
`布布`, `臭布布`, or `香布布`. The inverse self-name forms are rejected. Each
special nickname (`一二宝`, `臭布布`, `香布布`) may occur at most once, so the
dialogue does not sound mechanically branded. A strict complete 15–20-turn
script must contain at least one valid address in each direction. The fixed
three-turn opening is outside this dialogue check and remains unchanged.

## External model/cache configuration

F5-TTS normally resolves `F5TTS_v1_Base` from
`hf://SWivid/F5-TTS/F5TTS_v1_Base` into the user's Hugging Face cache. The
multilingual model is published under CC-BY-NC-4.0. The following optional
environment variables or equivalent profile fields select already-downloaded
external files:

| Environment variable | Profile field | Meaning |
|---|---|---|
| `PAPER_EAR_F5_CHECKPOINT` | `checkpoint_path` / `ckpt_file` | Model checkpoint file |
| `PAPER_EAR_F5_VOCAB` | `vocab_path` / `vocab_file` | Vocabulary file |
| `PAPER_EAR_F5_VOCODER_DIR` | `vocoder_dir` / `vocoder_local_path` | Local Vocos directory |
| `PAPER_EAR_F5_HF_CACHE_DIR` | `hf_cache_dir` | External Hugging Face cache directory |
| `PAPER_EAR_F5_DEVICE` | `device` | Optional PyTorch device, for example `cuda` or `cpu` |

Explicit files/directories are checked before model initialization. Weights
must remain outside the repository.

## Provenance and release boundary

- F5-TTS implementation: [SWivid/F5-TTS](https://github.com/SWivid/F5-TTS).
- Reference implementation and clips: [BoxAudio-0](https://github.com/Boxjod/box2audio-0), MIT repository at the pinned commit above.
- BoxAudio-0 credits 黄小B as the character-IP source. Repository visibility
  and code licensing do not by themselves prove permission to commercially
  exploit a character identity or voice likeness.
- The default F5TTS v1 Base model is non-commercial (CC-BY-NC-4.0). Do not
  describe this backend as cleared for commercial advertising without a
  separate rights review and any licenses required for the model, reference
  performances, and characters.
- Label published narration as AI-generated and unofficial unless the relevant
  rights holder has explicitly approved a different representation.
- For `bubu-yier-v1`, `verify_video.py --render-report ...` fails unless every
  intro and paper audio record proves the expected speaker-to-reference mapping,
  the role-specific pinned SHA-256, `F5TTS_v1_Base`, `spoken_text-only`, and
  `on-device`.
- A successful renderer report records SHA-256 digests for the PDF, dialogue
  script, and completed MP4. The branded media gate requires verified source
  binding, existing source/script paths, an exact report-output path match, and
  a freshly recomputed MP4 digest. A stale report or replaced video therefore
  cannot pass as the current branded deliverable.
