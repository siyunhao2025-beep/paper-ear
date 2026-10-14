#!/usr/bin/env python3
"""Render a privacy-safe Mandarin voice menu with Kokoro v1.1-zh + Misaki."""

import argparse
import html
import json
import sys
from pathlib import Path

from render_paper_video import KOKORO_ZH_MODEL, synthesize_turn_audio


VOICE_MENU = (
    {
        "voice": "zf_001",
        "speaker": "female",
        "label": "女声 A · 明快主讲",
        "traits": "明亮 · 利落 · 节奏最快",
        "measurement": "净语音约 6.58 秒｜相对中高响度｜基频约 261 Hz",
        "best_for": "快速概览、开场抓重点、短句式结论",
        "watch_for": "八个候选中语速最快；信息密集段落要多断句",
    },
    {
        "voice": "zf_018",
        "speaker": "female",
        "label": "女声 B · 轻柔讲解",
        "traits": "轻柔 · 高音 · 节奏舒缓",
        "measurement": "净语音约 8.15 秒｜相对最轻｜基频约 240 Hz",
        "best_for": "耐心解释、背景铺垫、温和的证据梳理",
        "watch_for": "响度较轻；与男声搭配时要检查音量平衡",
    },
    {
        "voice": "zf_046",
        "speaker": "female",
        "label": "女声 C · 沉稳分析",
        "traits": "中低音 · 轮廓清楚 · 节奏舒展",
        "measurement": "净语音约 8.34 秒｜相对中等响度｜基频约 174 Hz",
        "best_for": "方法拆解、限制讨论、较严肃的学术段落",
        "watch_for": "与低沉男声的音高反差较小，选角时注意角色区分",
    },
    {
        "voice": "zf_090",
        "speaker": "female",
        "label": "女声 D · 均衡主讲（推荐起点）",
        "traits": "温和 · 均衡 · 节奏舒展",
        "measurement": "净语音约 8.35 秒｜相对中等响度｜基频约 226 Hz",
        "best_for": "全文主讲、证据解读、长时间连续聆听",
        "watch_for": "不是情绪模型；激情仍要靠问答结构、标点和停顿",
    },
    {
        "voice": "zm_010",
        "speaker": "male",
        "label": "男声 A · 快速追问",
        "traits": "清爽 · 利落 · 节奏最快",
        "measurement": "净语音约 6.56 秒｜相对中等响度｜基频约 123 Hz",
        "best_for": "短促追问、快速反驳、观点交锋",
        "watch_for": "八个候选中节奏最快；长问题要拆成两句",
    },
    {
        "voice": "zm_033",
        "speaker": "male",
        "label": "男声 B · 厚实质疑（推荐起点）",
        "traits": "低沉 · 厚实 · 存在感强",
        "measurement": "净语音约 7.77 秒｜相对最响｜基频约 109 Hz",
        "best_for": "方法质疑、边界条件、审稿人式追问",
        "watch_for": "存在感较强；普通解释段不要连续使用高强度语气",
    },
    {
        "voice": "zm_066",
        "speaker": "male",
        "label": "男声 C · 温和讨论",
        "traits": "温和 · 较轻 · 中低音",
        "measurement": "净语音约 7.85 秒｜相对最轻｜基频约 126 Hz",
        "best_for": "合作式讨论、补充解释、友好反问",
        "watch_for": "响度偏轻；与明亮女声搭配时要检查混音平衡",
    },
    {
        "voice": "zm_098",
        "speaker": "male",
        "label": "男声 D · 稳重收束",
        "traits": "低沉 · 稳重 · 节奏最舒缓",
        "measurement": "净语音约 8.41 秒｜相对较响｜基频约 108 Hz",
        "best_for": "结论复盘、谨慎让步、未决问题收束",
        "watch_for": "节奏最慢；快节奏短视频中可能显得拖沓",
    },
)

DEFAULT_TEXT = "先别急着下结论。这项结果看起来很亮眼，但它真的排除了另一种解释吗？"


def write_selector(output_dir, manifest):
    cards = []
    defaults = {"female": "zf_090", "male": "zm_033"}
    headings = {"female": "女声主讲人", "male": "男声质疑者"}
    for speaker in ("female", "male"):
        speaker_cards = []
        for clip in manifest["clips"]:
            if clip["speaker"] != speaker or clip["status"] != "rendered":
                continue
            checked = " checked" if clip["voice"] == defaults[speaker] else ""
            choice = clip["label"].split("·", 1)[0].strip().split()[-1]
            speaker_cards.append(
                '<label class="voice-card">'
                f'<input type="radio" name="{speaker}" value="{html.escape(clip["voice"])}" data-choice="{html.escape(choice)}"{checked}>'
                '<span class="voice-copy">'
                f'<span class="voice-name">{html.escape(clip["label"])}</span>'
                f'<span class="voice-id">{html.escape(clip["voice"])}</span>'
                f'<span class="traits">{html.escape(clip["traits"])}</span>'
                f'<span class="measurement"><b>同句测量：</b>{html.escape(clip["measurement"])}</span>'
                f'<span class="choice-note"><b>适合：</b>{html.escape(clip["best_for"])}</span>'
                f'<span class="choice-note caution"><b>留意：</b>{html.escape(clip["watch_for"])}</span>'
                '</span>'
                f'<span class="duration">本次 {clip["duration_seconds"]:.2f} 秒</span>'
                f'<audio controls preload="metadata" src="{html.escape(clip["audio_file"])}"></audio>'
                "</label>"
            )
        cards.append(f'<section><h2>{headings[speaker]}</h2><div class="grid">{"".join(speaker_cards)}</div></section>')

    template = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Paper-Ear 普通话专用音色选择</title>
<style>
:root{color-scheme:light;font-family:"Microsoft YaHei",system-ui,sans-serif;background:#e9eff4;color:#17212b;--ink:#13293d;--signal:#e33b2e;--cyan:#087f8c;--line:#aebdca}
*{box-sizing:border-box}body{max-width:1120px;margin:0 auto;padding:28px 20px 70px;background-image:linear-gradient(#7890a214 1px,transparent 1px),linear-gradient(90deg,#7890a214 1px,transparent 1px);background-size:24px 24px}
header{position:relative;background:var(--ink);color:#fff;padding:30px 32px 26px;border-bottom:8px solid var(--signal);overflow:hidden}
header::after{content:"";position:absolute;right:28px;top:25px;width:180px;height:64px;opacity:.55;background:repeating-linear-gradient(90deg,transparent 0 7px,#55d6c2 8px 10px,transparent 11px 15px);clip-path:polygon(0 45%,8% 45%,12% 15%,17% 80%,22% 34%,27% 60%,34% 45%,100% 45%,100% 58%,35% 58%,27% 73%,22% 46%,17% 92%,12% 28%,8% 58%,0 58%)}
.badges{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px}.badge{border:1px solid #9ce7dc;color:#9ce7dc;padding:4px 8px;font-size:12px;font-weight:800;letter-spacing:.04em}.badge.alert{border-color:#ff9d92;color:#ffb1a9}
h1{font-family:Bahnschrift,"Microsoft YaHei",sans-serif;margin:0 0 12px;max-width:760px;font-size:clamp(30px,5vw,52px);line-height:1.05;letter-spacing:-.04em}header p{margin:8px 0;max-width:810px;line-height:1.75}.note{color:#9ce7dc;font-weight:700}.script{background:#ffffff13;border-left:4px solid #55d6c2;padding:8px 12px}
section{margin-top:34px;border-top:3px solid var(--ink);padding-top:10px}h2{font-family:Bahnschrift,"Microsoft YaHei",sans-serif;font-size:22px;margin:0 0 14px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.voice-card{display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:start;background:#fdfefe;padding:14px 14px 12px;border:1px solid var(--line);border-left:6px solid var(--line);cursor:pointer}
.voice-card:hover{border-left-color:var(--cyan)}.voice-card:focus-within{outline:3px solid #255ff4;outline-offset:2px}.voice-card:has(input:checked){border-left-color:var(--signal);background:#fff4f1}.voice-card input{accent-color:var(--signal);width:18px;height:18px}.voice-name{font-weight:800}.voice-id{font:600 11px Consolas,monospace;color:#6d7b87}.duration{font-size:12px;color:#526575;font-variant-numeric:tabular-nums}audio{grid-column:1/-1;width:100%;height:38px}
.voice-copy{display:grid;gap:4px}.traits{color:var(--cyan);font-weight:800;font-size:13px;letter-spacing:.02em}.measurement,.choice-note{font-size:12px;line-height:1.55;color:#435767}.measurement b,.choice-note b{color:var(--ink)}.choice-note.caution{color:#76594e}.duration{padding-top:2px;white-space:nowrap}
.result{position:sticky;bottom:10px;margin-top:30px;padding:14px 16px;border:2px solid #fff;background:var(--ink);color:#fff;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px 16px;align-items:center;box-shadow:8px 8px 0 #6f8798}.result-copy{display:grid;gap:7px}.return-note{margin:0;color:#9ce7dc;font-size:13px;font-weight:700}.reply-row{grid-column:1/-1;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px}.reply-row input{min-width:0;width:100%;border:2px solid #9ce7dc;background:#fff;color:var(--ink);padding:10px 12px;font:800 15px "Microsoft YaHei",sans-serif}
button{border:2px solid #fff;padding:10px 16px;background:var(--signal);color:#fff;font:800 15px "Microsoft YaHei",sans-serif;cursor:pointer}button:hover{background:#b92f25}button:focus-visible{outline:3px solid #55d6c2;outline-offset:3px}code{color:#9ce7dc;font-family:Bahnschrift,Consolas,monospace}@media(max-width:660px){body{padding:14px 10px 54px}header{padding:22px 18px 20px}header::after{display:none}.grid{grid-template-columns:1fr}.result{position:static;display:grid;grid-template-columns:1fr;box-shadow:5px 5px 0 #6f8798}.reply-row{grid-template-columns:1fr}.reply-row button{width:100%}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style></head><body>
<header><div class="badges"><span class="badge">普通话专用 v1.1</span><span class="badge">Misaki 中文发音器</span><span class="badge">本机离线</span><span class="badge alert">旧版试听已作废</span></div><h1>先听清每个字，再决定角色</h1><p>这 8 个候选全部改用中文专用 Kokoro v1.1-zh 模型和带声调的中文发音器，不再使用上一版发音含混的旧模型。每个声音说同一句标准普通话，播放器旁边直接写明特点、测量和适用角色。</p>
<p class="note">验收规则：先确认每个字都能听懂，再判断音色是否喜欢。文件能播放、模型能运行，都不等于普通话已经合格；最终以你的耳朵为准。</p><p class="script"><b>统一台词：</b>__TEXT__</p><p>这里不需要下载配置文件。试听并勾选后，复制页面底部那句话，回到原来的对话框发送即可；Paper-Ear 会从暂停处继续完成全部流程。</p></header>
__CARDS__
<div class="result"><div class="result-copy"><div>当前选择：女声 <code id="female-choice"></code> · 男声 <code id="male-choice"></code></div><p class="return-note" id="copy-status" aria-live="polite">听完后，把下面这句话发回原来的对话框。</p></div><div aria-hidden="true">试听 → 选择 → 回到对话</div><div class="reply-row"><input id="reply-text" readonly aria-label="发回对话框的音色选择"><button id="copy" type="button">复制选择，回到对话框</button></div></div>
<script>
function selectedElement(name){return document.querySelector('input[name="'+name+'"]:checked')}
function refresh(){const female=selectedElement('female'),male=selectedElement('male');document.getElementById('female-choice').textContent=female.dataset.choice+'（'+female.value+'）';document.getElementById('male-choice').textContent=male.dataset.choice+'（'+male.value+'）';document.getElementById('reply-text').value='女声 '+female.dataset.choice+'（'+female.value+'），男声 '+male.dataset.choice+'（'+male.value+'）';document.getElementById('copy-status').textContent='听完后，把下面这句话发回原来的对话框。'}
document.querySelectorAll('input[type=radio]').forEach(el=>el.addEventListener('change',refresh));refresh();
document.getElementById('copy').addEventListener('click',async()=>{const field=document.getElementById('reply-text'),status=document.getElementById('copy-status');try{await navigator.clipboard.writeText(field.value);status.textContent='已复制。现在回到原来的对话框并粘贴发送，我会接着完成。'}catch(error){field.focus();field.select();status.textContent='已选中这句话，请按 Ctrl+C 复制，然后回到原来的对话框发送。'}});
</script></body></html>"""
    page = template.replace("__TEXT__", html.escape(manifest["comparison_text"])).replace("__CARDS__", "".join(cards))
    selector_path = output_dir / "index.html"
    selector_path.write_text(page, encoding="utf-8")
    return selector_path


def main():
    parser = argparse.ArgumentParser(description="Render a dedicated Mandarin voice menu without opening a PDF.")
    parser.add_argument("--output-dir", required=True, help="Directory for WAV clips and manifest.json")
    parser.add_argument("--text", default=DEFAULT_TEXT, help="Same Mandarin comparison line spoken by every voice")
    parser.add_argument("--voices", help="Optional comma-separated subset of voice IDs")
    parser.add_argument("--model-dir", help="Optional directory containing the three Kokoro v1.1-zh model files")
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
        "voice_backend": "kokoro-zh-local",
        "model": KOKORO_ZH_MODEL,
        "language": "zh-CN",
        "g2p": "misaki-zh-1.1",
        "comparison_text": args.text,
        "privacy_scope": "The comparison text is synthesized on-device; no PDF is opened and no text is uploaded.",
        "sources": [
            "https://github.com/thewh1teagle/kokoro-onnx/blob/main/examples/chinese.py",
            "https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh",
        ],
        "quality_note": (
            "All clips use the dedicated v1.1 Chinese model and tone-aware Misaki ZHG2P. "
            "Technical generation success is not user listening approval; confirm intelligibility before a full render."
        ),
        "interaction_mode": "chat-first-resumable",
        "chat_reply_format": "女声 D（zf_090），男声 B（zm_033）",
        "default_chat_reply": "女声 D（zf_090），男声 B（zm_033）",
        "pause_contract": (
            "Listen locally, return to the same chat, and send both choices. "
            "No configuration download or user-run command is required."
        ),
        "clips": [],
    }

    for option in options:
        profile = {
            "voice": option["voice"],
            "model": KOKORO_ZH_MODEL,
            "rate": "+0%",
            "pitch": "+0Hz",
            "volume": "+0%",
            "style_degree": 1.0,
        }
        if args.model_dir:
            profile["model_dir"] = args.model_dir
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
            turn, "kokoro-zh-local", profile, str(wav_path)
        )
        record = {
            **option,
            **metadata,
            "audio_file": wav_path.name,
            "duration_seconds": round(duration, 3),
            "status": "rendered" if mode == "kokoro-zh-local" else "failed",
        }
        if error:
            record["error"] = error
        manifest["clips"].append(record)
        if mode != "kokoro-zh-local":
            wav_path.unlink(missing_ok=True)

    manifest["selector_file"] = write_selector(output_dir, manifest).name
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failures = [clip for clip in manifest["clips"] if clip["status"] != "rendered"]
    print(f"Rendered {len(manifest['clips']) - len(failures)}/{len(manifest['clips'])} Mandarin voice clips: {manifest_path}")
    print("Privacy: synthesis stayed on-device; no PDF was opened and no narration was uploaded.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
