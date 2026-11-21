#!/usr/bin/env python3
"""三向核对（初版）：字幕 vs 画面时长 vs 音频，把"对不上"列出来。

它只报能复现的部分：
- 字幕每条有没有落在音频的语音段里（需要 whisper-cli 才能做音频侧）；
- 文稿里的每句话有没有被念出来（按字二元组覆盖率，阈值 0.5）；
- 视频、字幕、语音的总时长是否一致（±0.3 s）。

没有检测到 whisper 时，明确报 partial（只做字幕-时长核对），不假装做过音频核对。

用法：
    python scripts/check_av.py --video v.mp4 --srt v.srt --script narration.txt \
        [--whisper whisper-cli.exe --model ggml-small.bin] [--lang zh]

退出码：0 全过；1 有对不上的项；2 输入缺失。
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError as e:
        class R:
            returncode = 127
            stdout = ""
            stderr = str(e)
        return R()


def srt_parse(path):
    raw = Path(path).read_text(encoding="utf-8-sig")
    cues = []
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        m = re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", lines[1] if "-->" not in lines[0] else lines[0])
        if not m:
            continue
        g = list(map(int, m.groups()))
        t0 = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        t1 = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        text = " ".join(lines[2:]) if "-->" in lines[1] else " ".join(lines[1:])
        cues.append({"t0": round(t0, 2), "t1": round(t1, 2), "text": text.strip()})
    return cues


def bigrams(s):
    s = re.sub(r"[\s，。！？、,.!?：:；;“”\"'（）()]", "", s)
    return {s[i:i + 2] for i in range(len(s) - 1)} or {s}


def coverage(line, transcript):
    a, b = bigrams(line), bigrams(transcript)
    return len(a & b) / max(1, len(a))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--srt")
    ap.add_argument("--script")
    ap.add_argument("--whisper")
    ap.add_argument("--model")
    ap.add_argument("--lang", default="zh")
    ap.add_argument("--ffmpeg", default="ffmpeg", help="ffmpeg 可执行文件（不在 PATH 里时给绝对路径）")
    ap.add_argument("--ffprobe", default="ffprobe", help="ffprobe 可执行文件（不在 PATH 里时给绝对路径）")
    ap.add_argument("--frames", metavar="DIR", help="把每条字幕中点的一帧抽出来（画面核对用；给人或视觉模型看，不自动判）")
    ap.add_argument("--sheet", metavar="FILE", help="把抽出的帧拼成一张联系表（需要 ffmpeg）")
    args = ap.parse_args()
    FF, FP = args.ffmpeg, args.ffprobe

    video = Path(args.video)
    if not video.exists():
        print("video not found", file=sys.stderr)
        return 2

    report = {"video": str(video), "status": "partial", "checks": []}

    # 1) 总时长
    probe = run([FP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)])
    dur = None
    if probe.returncode == 0 and probe.stdout.strip():
        dur = float(probe.stdout.strip())
    else:
        # 没有 ffprobe 时，用 ffmpeg 的 stderr 里那行 Duration 兜底
        alt = run([FF, "-hide_banner", "-i", str(video)])
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", alt.stderr or "")
        if m:
            dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    if dur is None:
        report["checks"].append({"name": "duration", "ok": False, "why": "ffprobe/ffmpeg 都不可用，读不到时长"})
    else:
        report["duration"] = round(dur, 2)
        if args.srt:
            cues = srt_parse(args.srt)
            report["cues"] = len(cues)
            if cues:
                last = max(c["t1"] for c in cues)
                report["checks"].append({
                    "name": "srt_end_matches_video",
                    "ok": abs(last - dur) <= 0.3,
                    "why": f"字幕末条结束 {last:.2f}s，视频 {dur:.2f}s",
                })

    # 2) 音频侧（可选）
    if not (args.whisper and args.model):
        report["checks"].append({"name": "audio_transcript", "ok": None, "why": "未提供 whisper，音频核对跳过（partial）"})
    elif args.srt:
        with tempfile.TemporaryDirectory() as td:
            wav = Path(td) / "a.wav"
            ex = run([FF, "-v", "error", "-y", "-i", str(video), "-ac", "1", "-ar", "16000", str(wav)])
            if ex.returncode != 0:
                report["checks"].append({"name": "extract_audio", "ok": False, "why": "ffmpeg 抽音轨失败"})
            else:
                out = Path(td) / "t"
                tr = run([args.whisper, "-m", args.model, "-f", str(wav), "-l", args.lang, "-oj", "-of", str(out)])
                jf = Path(str(out) + ".json")
                if tr.returncode != 0 or not jf.exists():
                    report["checks"].append({"name": "transcribe", "ok": False, "why": "whisper 转写失败"})
                else:
                    data = json.loads(jf.read_text(encoding="utf-8"))
                    segs = []
                    for s in data.get("transcription", []):
                        o = s.get("offsets", {})
                        segs.append({"t0": o.get("from", 0) / 1000, "t1": o.get("to", 0) / 1000, "text": s.get("text", "")})
                    report["transcript_segments"] = len(segs)
                    # 每条字幕是否落在语音段里
                    gaps = []
                    for c in srt_parse(args.srt):
                        overlap = 0.0
                        for s in segs:
                            overlap = max(overlap, min(c["t1"], s["t1"]) - max(c["t0"], s["t0"]))
                        if overlap < 0.5 * (c["t1"] - c["t0"]):
                            gaps.append({"cue": c["text"][:18], "t0": c["t0"], "t1": c["t1"], "overlap": round(overlap, 2)})
                    report["checks"].append({
                        "name": "cues_covered_by_speech",
                        "ok": not gaps,
                        "why": f"{len(gaps)} 条字幕没有语音覆盖" if gaps else "全部字幕落在语音段内",
                        "gaps": gaps[:8],
                    })
                    # 文稿每句是否被念出（按整段转写算覆盖率，再做时间窗定位）
                    if args.script:
                        lines = [l.strip() for l in Path(args.script).read_text(encoding="utf-8").splitlines() if l.strip()]
                        full = "".join(s["text"] for s in segs)
                        missing = []
                        for ln in lines:
                            cov = coverage(ln, full)
                            if cov < 0.5:
                                missing.append({"line": ln[:20], "coverage": round(cov, 2)})
                        report["checks"].append({
                            "name": "script_lines_spoken",
                            "ok": None if missing else True,
                            "why": (
                                f"{len(missing)} 句文稿覆盖率 <0.5——转写在音乐/音效下不可靠，需人耳复核；"
                                "不据此判失败" if missing else "文稿每句都能在转写里找到"
                            ),
                            "missing": missing[:8],
                        })
                    report["status"] = "full"

    if args.srt and args.frames:
        # 画面侧：每条字幕抽一帧，交给"眼睛"（人或视觉模型）；脚本不替你看图下结论。
        out = Path(args.frames)
        out.mkdir(parents=True, exist_ok=True)
        shots = []
        for i, c in enumerate(srt_parse(args.srt), 1):
            mid = (c["t0"] + c["t1"]) / 2
            dst = out / f"cue_{i:02d}.jpg"
            r = run([FF, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{mid:.2f}", "-i", str(video), "-frames:v", "1", str(dst)])
            if r.returncode == 0 and dst.exists():
                shots.append({"cue": i, "text": c["text"][:24], "at": round(mid, 2), "file": str(dst)})
        report["frames"] = shots
        report["checks"].append({
            "name": "frames_for_visual_review",
            "ok": None if shots else False,
            "why": f"抽了 {len(shots)} 帧，画面是否与字幕对得上需要人/视觉模型看；脚本不自动判" if shots else "抽帧失败",
        })
        if shots and args.sheet:
            # 联系表优先用 Pillow（不依赖 ffmpeg 的 glob 行为），没有 Pillow 再退回 ffmpeg
            made = False
            try:
                from PIL import Image
                cols = 3
                thumbs = []
                for s in shots:
                    im = Image.open(s["file"])
                    w = 480
                    h = round(im.height * w / im.width)
                    thumbs.append(im.resize((w, h)))
                rows = (len(thumbs) + cols - 1) // cols
                cw = max(t.width for t in thumbs)
                ch = max(t.height for t in thumbs)
                sheet = Image.new("RGB", (cw * cols, ch * rows), (20, 16, 12))
                for i, t in enumerate(thumbs):
                    sheet.paste(t, ((i % cols) * cw, (i // cols) * ch))
                sheet.save(args.sheet, quality=88)
                made = True
            except Exception:
                made = False
            if not made:
                cols = 3
                rows = max(1, (len(shots) + cols - 1) // cols)
                r = run([FF, "-hide_banner", "-loglevel", "error", "-y", "-pattern_type", "glob", "-i", str(out / "cue_*.jpg"),
                         "-filter_complex", f"scale=480:-1,tile={cols}x{rows}", "-frames:v", "1", args.sheet])
                made = r.returncode == 0
            report["sheet"] = args.sheet if made else None

    failed = [c for c in report["checks"] if c["ok"] is False]
    warned = [c for c in report["checks"] if c["ok"] is None]
    report["summary"] = {"fail": len(failed), "warn": len(warned)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
