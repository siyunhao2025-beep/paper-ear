#!/usr/bin/env python3
"""Render a privacy-safe local Mandarin voice menu through Lemonade/Kokoro."""

import argparse
import html
import json
import sys
from pathlib import Path

from render_paper_video import synthesize_turn_audio


VOICE_MENU = (
    {
        "voice": "zf_xiaobei",
        "speaker": "female",
        "label": "女声 A / zf_xiaobei",
        "traits": "舒缓 · 克制 · 留白较多",
        "best_for": "论文主讲、证据拆解、需要听清逻辑的段落",
        "watch_for": "同句试听中用时最长；快节奏短视频可能显慢",
    },
    {
        "voice": "zf_xiaoni",
        "speaker": "female",
        "label": "女声 B / zf_xiaoni",
        "traits": "清楚 · 匀速 · 存在感适中",
        "best_for": "摘要导读、方法讲解、通用型主讲",
        "watch_for": "风格较中性，强冲突场景需靠台词和剪辑补张力",
    },
    {
        "voice": "zf_xiaoxiao",
        "speaker": "female",
        "label": "女声 C / zf_xiaoxiao",
        "traits": "明亮 · 饱满 · 响度更突出",
        "best_for": "开场抓人、亮点宣布、结论强调",
        "watch_for": "连续高信息密度段落可能显得偏满",
    },
    {
        "voice": "zf_xiaoyi",
        "speaker": "female",
        "label": "女声 D / zf_xiaoyi",
        "traits": "高亮 · 轻快 · 年轻感较强",
        "best_for": "轻量科普、快速浏览、活跃型主持",
        "watch_for": "本组基频最高；严肃审证场景可能不够沉稳",
    },
    {
        "voice": "zm_yunjian",
        "speaker": "male",
        "label": "男声 A / zm_yunjian",
        "traits": "低沉 · 稳重 · 质疑感明确",
        "best_for": "审稿人、方法质疑、边界条件追问",
        "watch_for": "音量相对克制，混音时可略提高对白增益",
    },
    {
        "voice": "zm_yunxi",
        "speaker": "male",
        "label": "男声 B / zm_yunxi",
        "traits": "中低音 · 利落 · 对话反应快",
        "best_for": "年轻讨论者、短促追问、观点交锋",
        "watch_for": "声音较轻，长篇总结的权威感相对弱",
    },
    {
        "voice": "zm_yunxia",
        "speaker": "male",
        "label": "男声 C / zm_yunxia",
        "traits": "高亮 · 温和 · 语速偏舒展",
        "best_for": "协作者、补充解释、友好型反问",
        "watch_for": "本次实测音高偏高；与高音女声搭配时角色反差较小",
    },
    {
        "voice": "zm_yunyang",
        "speaker": "male",
        "label": "男声 D / zm_yunyang",
        "traits": "低音 · 快速 · 简洁有力",
        "best_for": "主持收束、结论追问、短句质疑",
        "watch_for": "同句试听中最快且最轻，需留意吞字与响度",
    },
)

DEFAULT_TEXT = "先别急着下结论。这个结果看起来很漂亮，但它真的排除了另一种解释吗？"


def write_selector(output_dir, manifest):
    cards = []
    defaults = {"female": "zf_xiaobei", "male": "zm_yunjian"}
    headings = {"female": "女声主讲人", "male": "男声质疑者"}
    for speaker in ("female", "male"):
        speaker_cards = []
        for clip in manifest["clips"]:
            if clip["speaker"] != speaker or clip["status"] != "rendered":
                continue
            checked = " checked" if clip["voice"] == defaults[speaker] else ""
            speaker_cards.append(
                '<label class="voice-card">'
                f'<input type="radio" name="{speaker}" value="{html.escape(clip["voice"])}"{checked}>'
                '<span class="voice-copy">'
                f'<span class="voice-name">{html.escape(clip["label"])}</span>'
                f'<span class="traits">{html.escape(clip["traits"])}</span>'
                f'<span class="choice-note"><b>适合：</b>{html.escape(clip["best_for"])}</span>'
                f'<span class="choice-note caution"><b>留意：</b>{html.escape(clip["watch_for"])}</span>'
                '</span>'
                f'<span class="duration">{clip["duration_seconds"]:.2f} 秒</span>'
                f'<audio controls preload="metadata" src="{html.escape(clip["audio_file"])}"></audio>'
                "</label>"
            )
        cards.append(f'<section><h2>{headings[speaker]}</h2><div class="grid">{"".join(speaker_cards)}</div></section>')

    template = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Paper-Ear 本地音色选择</title>
<style>
:root{color-scheme:light;font-family:"Microsoft YaHei",system-ui,sans-serif;background:#e9eff4;color:#17212b;--ink:#13293d;--signal:#e33b2e;--cyan:#087f8c;--line:#aebdca}
*{box-sizing:border-box}body{max-width:1120px;margin:0 auto;padding:28px 20px 70px;background-image:linear-gradient(#7890a214 1px,transparent 1px),linear-gradient(90deg,#7890a214 1px,transparent 1px);background-size:24px 24px}
header{position:relative;background:var(--ink);color:#fff;padding:30px 32px 26px;border-bottom:8px solid var(--signal);overflow:hidden}
header::after{content:"";position:absolute;right:28px;top:25px;width:180px;height:64px;opacity:.55;background:repeating-linear-gradient(90deg,transparent 0 7px,#55d6c2 8px 10px,transparent 11px 15px);clip-path:polygon(0 45%,8% 45%,12% 15%,17% 80%,22% 34%,27% 60%,34% 45%,100% 45%,100% 58%,35% 58%,27% 73%,22% 46%,17% 92%,12% 28%,8% 58%,0 58%)}
h1{font-family:Bahnschrift,"Microsoft YaHei",sans-serif;margin:0 0 12px;max-width:760px;font-size:clamp(30px,5vw,52px);line-height:1.05;letter-spacing:-.04em}header p{margin:8px 0;max-width:780px;line-height:1.75}.note{color:#9ce7dc;font-weight:700}
section{margin-top:34px;border-top:3px solid var(--ink);padding-top:10px}h2{font-family:Bahnschrift,"Microsoft YaHei",sans-serif;font-size:22px;margin:0 0 14px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.voice-card{display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:start;background:#fdfefe;padding:14px 14px 12px;border:1px solid var(--line);border-left:6px solid var(--line);cursor:pointer}
.voice-card:hover{border-left-color:var(--cyan)}.voice-card:focus-within{outline:3px solid #255ff4;outline-offset:2px}.voice-card:has(input:checked){border-left-color:var(--signal);background:#fff4f1}.voice-card input{accent-color:var(--signal);width:18px;height:18px}.voice-name{font-weight:800}.duration{font-size:12px;color:#526575;font-variant-numeric:tabular-nums}audio{grid-column:1/-1;width:100%;height:38px}
.voice-copy{display:grid;gap:4px}.traits{color:var(--cyan);font-weight:800;font-size:13px;letter-spacing:.02em}.choice-note{font-size:12px;line-height:1.55;color:#435767}.choice-note b{color:var(--ink)}.choice-note.caution{color:#76594e}.duration{padding-top:2px;white-space:nowrap}
.result{position:sticky;bottom:10px;margin-top:30px;padding:14px 16px;border:2px solid #fff;background:var(--ink);color:#fff;display:flex;gap:16px;align-items:center;justify-content:space-between;flex-wrap:wrap;box-shadow:8px 8px 0 #6f8798}
button{border:2px solid #fff;padding:10px 16px;background:var(--signal);color:#fff;font:800 15px "Microsoft YaHei",sans-serif;cursor:pointer}button:hover{background:#b92f25}button:focus-visible{outline:3px solid #55d6c2;outline-offset:3px}code{color:#9ce7dc;font-family:Bahnschrift,Consolas,monospace}@media(max-width:660px){body{padding:14px 10px 54px}header{padding:22px 18px 20px}header::after{display:none}.grid{grid-template-columns:1fr}.result{position:static;box-shadow:5px 5px 0 #6f8798}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style></head><body>
<header><h1>先听，再定角色</h1><p>这是 Paper-Ear 的本地组会调音台。8 个免费普通话预设说同一句话；每张卡片都写明听感、适合角色和使用提醒，方便先看标签、再用耳朵确认。</p>
<p class="note">标签边界：特点来自本机同句试听的时长、相对音高与响度，以及面向论文对话的选角判断；不是官方人格定义。Kokoro 官方把这些普通话预设标为 D 级，它适合离线预览，不等于真人演员或强情绪模型。</p><p>统一台词：__TEXT__</p></header>
__CARDS__
<div class="result"><div>当前选择：女声 <code id="female-choice"></code> · 男声 <code id="male-choice"></code></div><button id="download">下载选角 JSON</button></div>
<script>
function selected(name){const el=document.querySelector('input[name="'+name+'"]:checked');return el?el.value:''}
function refresh(){document.getElementById('female-choice').textContent=selected('female');document.getElementById('male-choice').textContent=selected('male')}
document.querySelectorAll('input[type=radio]').forEach(el=>el.addEventListener('change',refresh));refresh();
document.getElementById('download').addEventListener('click',()=>{const female=selected('female'),male=selected('male');const data={voice_backend:'lemonade-local',voice_model:'kokoro-v1',female_voice:female,male_voice:male,voice_profiles:{female:{model:'kokoro-v1',voice:female},male:{model:'kokoro-v1',voice:male}}};const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));a.download='paper-ear-local-cast.json';a.click();URL.revokeObjectURL(a.href)});
</script></body></html>"""
    page = template.replace("__TEXT__", html.escape(manifest["comparison_text"])).replace("__CARDS__", "".join(cards))
    selector_path = output_dir / "index.html"
    selector_path.write_text(page, encoding="utf-8")
    return selector_path


def main():
    parser = argparse.ArgumentParser(description="Render the tested local Mandarin voice menu without opening a PDF.")
    parser.add_argument("--output-dir", required=True, help="Directory for WAV clips and manifest.json")
    parser.add_argument("--text", default=DEFAULT_TEXT, help="Same comparison line spoken by every voice")
    parser.add_argument("--voices", help="Optional comma-separated subset of voice IDs")
    parser.add_argument("--base-url", help="Optional Lemonade base URL; loopback is required unless explicitly allowed")
    args = parser.parse_args()

    requested = None
    if args.voices:
        requested = {item.strip() for item in args.voices.split(",") if item.strip()}
    options = [item for item in VOICE_MENU if requested is None or item["voice"] in requested]
    known = {item["voice"] for item in VOICE_MENU}
    unknown = sorted((requested or set()) - known)
    if unknown:
        raise ValueError(f"Unknown menu voice(s): {', '.join(unknown)}")
    if not options:
        raise ValueError("No voices selected.")

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "voice_backend": "lemonade-local",
        "model": "kokoro-v1",
        "comparison_text": args.text,
        "privacy_scope": "The comparison text is synthesized on the configured Lemonade endpoint; no PDF is opened.",
        "source": "https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md",
        "quality_note": (
            "Kokoro's upstream card grades the Mandarin presets D overall and warns that non-English support is thin. "
            "Treat these clips as a free offline preview, not proof of human-level emotional acting."
        ),
        "clips": [],
    }

    for option in options:
        profile = {
            "voice": option["voice"],
            "model": "kokoro-v1",
            "rate": "+0%",
            "pitch": "+0Hz",
            "volume": "+0%",
            "style_degree": 1.0,
        }
        if args.base_url:
            profile["base_url"] = args.base_url
        turn = {
            "speaker": option["speaker"],
            "spoken_text": args.text,
            "emotion": "skeptical",
            "emotion_intensity": 0.62,
            "delivery": {
                "provider_style": "skeptical but respectful",
                "style_degree": 1.0,
                "rate": "+0%",
                "pitch": "+0Hz",
                "volume": "+0%",
                "pause_before_ms": 120,
                "pause_after_ms": 280,
                "emphasis_terms": [],
            },
        }
        wav_path = output_dir / f"{option['voice']}.wav"
        duration, mode, error, metadata = synthesize_turn_audio(
            turn, "lemonade-local", profile, str(wav_path)
        )
        record = {
            **option,
            **metadata,
            "audio_file": wav_path.name,
            "duration_seconds": round(duration, 3),
            "status": "rendered" if mode == "lemonade-local" else "failed",
        }
        if error:
            record["error"] = error
        manifest["clips"].append(record)
        if mode != "lemonade-local":
            wav_path.unlink(missing_ok=True)

    manifest["selector_file"] = write_selector(output_dir, manifest).name
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failures = [clip for clip in manifest["clips"] if clip["status"] != "rendered"]
    print(f"Rendered {len(manifest['clips']) - len(failures)}/{len(manifest['clips'])} local voice clips: {manifest_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
