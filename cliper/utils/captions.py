"""Dynamic word-level subtitles: faster-whisper transcription + styled karaoke ASS.

Transcribes the SHORT clip (cheap, runs on Mac CPU) to get word timestamps, then emits an ASS
file where the currently-spoken word is highlighted within a small rolling line. Burned via
libass downstream (utils.ffmpeg.burn_subtitles). Several visual STYLES are selectable per niche.
"""
from __future__ import annotations

from pathlib import Path

# ASS colours are &HAABBGGRR (alpha, blue, green, red).
_WHITE = "&H00FFFFFF"

# Selectable caption presets. `align` is ASS \an (2=bottom-center, 5=middle-center).
# `max_chars` caps the line WIDTH so text never overflows the 1080px frame; `max_per_line`
# caps the word count. Lines break on whichever hits first (or a speech gap).
STYLES: dict[str, dict] = {
    "classic": dict(font="Arial", fontsize=84, primary=_WHITE, highlight="&H0000F0FF",
                    outline=5, shadow=1, align=2, margin_v=360, uppercase=False,
                    max_per_line=4, max_chars=16),
    "hormozi": dict(font="Arial", fontsize=100, primary=_WHITE, highlight="&H0000FF00",
                    outline=6, shadow=0, align=5, margin_v=0, uppercase=True,
                    max_per_line=3, max_chars=13),
    "minimal": dict(font="Arial", fontsize=76, primary=_WHITE, highlight=_WHITE,
                    outline=3, shadow=1, align=2, margin_v=300, uppercase=False,
                    max_per_line=4, max_chars=20),
}


def load_model(name: str = "small", device: str = "cpu"):
    from faster_whisper import WhisperModel

    compute_type = "int8" if device == "cpu" else "float16"
    return WhisperModel(name, device=device, compute_type=compute_type)


def transcribe_words(model, path, language=None) -> list[dict]:
    """Return [{start, end, word}] with word-level timestamps (language auto-detected if None)."""
    segments, _info = model.transcribe(str(path), word_timestamps=True, vad_filter=True,
                                       language=language)
    words: list[dict] = []
    for seg in segments:
        for w in (seg.words or []):
            token = w.word.strip()
            if token:
                words.append({"start": float(w.start), "end": float(w.end), "word": token})
    return words


def transcribe_segments(model, path, language=None) -> list[dict]:
    """Return [{start, end, text}] at segment level (for whole-video moment selection)."""
    segments, _info = model.transcribe(str(path), vad_filter=True, language=language)
    return [{"start": float(s.start), "end": float(s.end), "text": s.text.strip()}
            for s in segments if s.text.strip()]


def _ass_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _group_words(words: list[dict], max_per_line: int, max_chars: int,
                 max_gap: float = 0.6) -> list[list[dict]]:
    """Break the word stream into short rolling lines.

    A line breaks before a word that would exceed `max_chars` (keeps text inside the frame),
    `max_per_line` words, or after a speech gap. A single over-long word still gets its own line.
    """
    lines: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        if cur:
            projected = sum(len(x["word"]) for x in cur) + len(cur) + len(w["word"])
            if (len(cur) >= max_per_line or projected > max_chars
                    or w["start"] - cur[-1]["end"] > max_gap):
                lines.append(cur)
                cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    return lines


def _render_line(line: list[dict], active: int, style: dict) -> str:
    parts = []
    for j, w in enumerate(line):
        word = w["word"].replace("{", "(").replace("}", ")")
        if style["uppercase"]:
            word = word.upper()
        if j == active:
            parts.append(f"{{\\c{style['highlight']}\\fscx110\\fscy110}}{word}{{\\r}}")
        else:
            parts.append(word)
    return " ".join(parts)


def write_ass(words: list[dict], path, *, style: str = "classic", position: str | None = None,
              width: int = 1080, height: int = 1920) -> Path:
    """Write a karaoke ASS where each word's event highlights that word within its line.

    `style` selects a preset from STYLES. `position` ('lower'|'center'), if given, overrides the
    preset's vertical placement.
    """
    st = dict(STYLES.get(style, STYLES["classic"]))
    if position == "lower":
        st["align"], st["margin_v"] = 2, 360
    elif position == "center":
        st["align"], st["margin_v"] = 5, 0

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {width}\nPlayResY: {height}\n"
        "WrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Sub,{st['font']},{st['fontsize']},{st['primary']},&H000000FF,&H00000000,"
        f"&H64000000,1,0,0,0,100,100,0,0,1,{st['outline']},{st['shadow']},{st['align']},"
        f"90,90,{st['margin_v']},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    events = []
    for line in _group_words(words, st["max_per_line"], st["max_chars"]):
        for i, w in enumerate(line):
            events.append(
                f"Dialogue: 0,{_ass_time(w['start'])},{_ass_time(w['end'])},Sub,,0,0,0,,"
                f"{_render_line(line, i, st)}"
            )
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return path
