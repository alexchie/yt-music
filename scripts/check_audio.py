"""Find songs whose later part gains a second, clashing chord layer.

Some generated tracks start clean and then, part way through, a second
instrument starts strumming chords in another key on top of the song, so it
sounds like two tracks playing at once. This script listens for that: it
compares every 10-second window of a song with the song's own opening, and
flags stretches where the harmony suddenly gets muddier and less in key
(more clashing semitones, flatter pitch-class spread, weaker key fit) or the
left/right channels stop matching, for at least `--min-seconds` in a row.

Usage:
  python scripts/check_audio.py music/                    # every track in the library
  python scripts/check_audio.py song.mp3 other.wav        # single files
  python scripts/check_audio.py video.mp4 --chapters video_en_description.txt
      # a finished video, checked track by track using the description's tracklist

Exit code is 1 when anything was flagged and --strict is given, else 0.
A JSON report can be written with --json report.json.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
AUDIO_EXT = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus", ".mp4", ".mkv", ".mov", ".webm"}

SR = 22050
N_FFT = 8192
HOP = 2048
WINDOW_S = 10.0      # analysis window
STEP_S = 2.0         # window step
SKIP_INTRO_S = 8.0   # fades / intros are not representative
BASELINE_FRAC = 0.35  # the opening part of a song that serves as its own reference

# Krumhansl-Kessler key profiles.
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
KEYS = np.array([np.roll(MAJOR, k) for k in range(12)] + [np.roll(MINOR, k) for k in range(12)])
KEYS = (KEYS - KEYS.mean(1, keepdims=True)) / KEYS.std(1, keepdims=True)
KEY_NAMES = [n for n in "C C# D D# E F F# G G# A A# B".split()] + \
            [n + "m" for n in "C C# D D# E F F# G G# A A# B".split()]


def decode(path):
    """Stereo float32 at SR, shape (n, 2)."""
    raw = subprocess.run(
        [FFMPEG, "-v", "error", "-i", str(path), "-map", "0:a:0", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)


def chroma_frames(x):
    """12-bin pitch-class energy per STFT frame of a mono signal (computed in chunks
    so hour-long files stay small in memory)."""
    if len(x) < N_FFT:
        x = np.pad(x, (0, N_FFT - len(x)))
    n = 1 + (len(x) - N_FFT) // HOP
    win = np.hanning(N_FFT).astype(np.float32)
    out = np.empty((n, 12), dtype=np.float32)
    for s in range(0, n, 256):
        idx = np.arange(N_FFT)[None, :] + HOP * np.arange(s, min(n, s + 256))[:, None]
        spec = np.abs(np.fft.rfft(x[idx] * win, axis=1)).astype(np.float32)
        # Spectral whitening per frame tames loud bass so chord tones count.
        spec = spec / (np.median(spec, axis=1, keepdims=True) + 1e-6)
        spec = np.maximum(spec - 1.0, 0) ** 0.5
        out[s:s + 256] = spec @ CHROMA
    return out


def chroma_matrix():
    """Bins -> 12 pitch classes, 65 Hz .. 2.1 kHz (bass notes up to upper chord tones)."""
    freqs = np.fft.rfftfreq(N_FFT, 1 / SR)
    m = np.zeros((len(freqs), 12), dtype=np.float32)
    ok = (freqs >= 65) & (freqs <= 2100)
    midi = 69 + 12 * np.log2(freqs[ok] / 440.0)
    nearest = np.round(midi)
    # Only bins close to a semitone centre count, so noise and drums smear less.
    weight = np.clip(1 - 2.5 * np.abs(midi - nearest), 0, 1)
    m[np.where(ok)[0], (nearest.astype(int) % 12)] = weight
    return m


CHROMA = chroma_matrix()


def window_features(audio):
    """One row per window: dissonance, chroma entropy, key fit, L/R correlation, best key."""
    chroma = chroma_frames(audio.mean(1))
    frame_t = (np.arange(len(chroma)) * HOP + N_FFT / 2) / SR

    win_f = int(WINDOW_S * SR / HOP)
    step_f = max(1, int(STEP_S * SR / HOP))
    rows = []
    for s in range(0, max(1, len(chroma) - win_f + 1), step_f):
        c = chroma[s:s + win_f].sum(0)
        if c.sum() <= 1e-6:
            continue
        p = c / c.sum()
        entropy = -(p * np.log(p + 1e-12)).sum() / np.log(12)
        # Energy sitting a semitone (or tritone) apart from other energy = clashing notes.
        diss = (p * np.roll(p, 1)).sum() * 2 + (p * np.roll(p, 6)).sum()
        z = (p - p.mean()) / (p.std() + 1e-9)
        fits = KEYS @ z / 12
        a0 = int(frame_t[s] * SR)
        a1 = min(len(audio), int(frame_t[min(s + win_f, len(frame_t) - 1)] * SR))
        seg = audio[a0:a1]
        lr = float(np.corrcoef(seg[:, 0], seg[:, 1])[0, 1]) if len(seg) > 10 and seg.std(0).min() > 1e-5 else 1.0
        rows.append((frame_t[s] - N_FFT / 2 / SR, diss, entropy, fits.max(), lr, int(fits.argmax())))
    return np.array(rows, dtype=np.float64)


def robust_z(values, ref, floor):
    """Distance from the opening's median in units of its spread.

    `floor` is the smallest change that matters musically, so a very steady
    opening does not make tiny wobbles look huge."""
    med = np.median(ref)
    mad = np.median(np.abs(ref - med)) * 1.4826
    return (values - med) / max(mad, floor)


def analyse(audio, start_offset=0.0, threshold=2.5, min_seconds=20.0):
    """Return a dict with flagged ranges (seconds, absolute) for one song."""
    dur = len(audio) / SR
    result = {"duration": round(dur, 1), "flagged": [], "score_max": 0.0}
    if dur < 60:
        return result
    f = window_features(audio)
    if len(f) < 10:
        return result
    t, diss, ent, fit, lr, key = f.T
    base = (t >= SKIP_INTRO_S) & (t <= max(SKIP_INTRO_S + 30, dur * BASELINE_FRAC))
    if base.sum() < 5:
        return result
    # Higher = worse for every component.
    score = np.mean([
        robust_z(diss, diss[base], 0.01),
        robust_z(ent, ent[base], 0.015),
        -robust_z(fit, fit[base], 0.05),
    ], axis=0)
    lr_drop = np.clip(-robust_z(lr, lr[base], 0.03), 0, None)
    score = score + 0.5 * np.clip(lr_drop - 2, 0, None)
    # Smooth over ~20 s so a single odd chord does not trigger it.
    k = max(1, int(20 / STEP_S))
    smooth = np.convolve(score, np.ones(k) / k, mode="same")

    # Leave out the last 10 s: outros and the crossfade into the next song.
    usable = (t > dur * BASELINE_FRAC) & (t + WINDOW_S < dur - 10)
    hot = (smooth > threshold) & usable
    base_key = KEY_NAMES[int(np.bincount(key[base].astype(int), minlength=24).argmax())]
    ranges, i = [], 0
    while i < len(hot):
        if hot[i]:
            j = i
            while j + 1 < len(hot) and hot[j + 1]:
                j += 1
            a, b = t[i], t[j] + WINDOW_S
            if b - a >= min_seconds:
                seg_keys = key[i:j + 1].astype(int)
                ranges.append({
                    "start": round(start_offset + a, 1),
                    "end": round(start_offset + b, 1),
                    "score": round(float(smooth[i:j + 1].max()), 2),
                    "key_before": base_key,
                    "key_during": KEY_NAMES[int(np.bincount(seg_keys, minlength=24).argmax())],
                    "lr_corr_before": round(float(np.median(lr[base])), 2),
                    "lr_corr_during": round(float(np.median(lr[i:j + 1])), 2),
                })
            i = j + 1
        else:
            i += 1
    result["flagged"] = ranges
    result["score_max"] = round(float(smooth[usable].max()) if usable.any() else 0.0, 2)
    return result


def parse_chapters(path):
    """[(start_seconds, name)] from a description file's tracklist lines like '12:34 Name'."""
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(?:(\d+):)?(\d{1,2}):(\d{2})\s+(.+)$", line.strip())
        if m:
            h, mi, s, name = m.groups()
            out.append((int(h or 0) * 3600 + int(mi) * 60 + int(s), name.strip()))
    return out


def clock(sec):
    sec = int(sec)
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="audio/video files or folders")
    ap.add_argument("--chapters", help="description .txt whose tracklist splits a single video into songs")
    ap.add_argument("--threshold", type=float, default=2.5, help="score needed to flag (default 2.5)")
    ap.add_argument("--min-seconds", type=float, default=20.0, help="shortest stretch to flag (default 20)")
    ap.add_argument("--json", help="write the full report here")
    ap.add_argument("--strict", action="store_true", help="exit 1 when anything is flagged")
    args = ap.parse_args()

    files = []
    for p in map(Path, args.paths):
        files += sorted(q for q in p.rglob("*") if q.suffix.lower() in AUDIO_EXT) if p.is_dir() else [p]
    if not files:
        sys.exit("No audio files found")

    report, flagged = [], 0
    for path in files:
        try:
            audio = decode(path)
        except subprocess.CalledProcessError as e:
            print(f"SKIP  {path.name}: cannot decode ({e.stderr.decode(errors='replace').strip()[:120]})")
            continue
        songs = [(0.0, len(audio) / SR, path.name)]
        if args.chapters:
            ch = parse_chapters(args.chapters)
            ends = [s for s, _ in ch[1:]] + [len(audio) / SR]
            songs = [(s, e, n) for (s, n), e in zip(ch, ends)]
        for start, end, name in songs:
            r = analyse(audio[int(start * SR):int(end * SR)], start, args.threshold, args.min_seconds)
            r["name"] = name
            r["file"] = str(path)
            report.append(r)
            if r["flagged"]:
                flagged += 1
                spans = ", ".join(
                    f"{clock(x['start'])}-{clock(x['end'])} (score {x['score']}, key {x['key_before']}->{x['key_during']})"
                    for x in r["flagged"]
                )
                print(f"FLAG  {name}  [{clock(r['duration'])}]  {spans}")
            else:
                print(f"ok    {name}  [{clock(r['duration'])}]  max score {r['score_max']}")

    print(f"\n{flagged} of {len(report)} song(s) flagged")
    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.exit(1 if args.strict and flagged else 0)


if __name__ == "__main__":
    main()
