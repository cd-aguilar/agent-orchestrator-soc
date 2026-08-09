"""
One-off script: renders a real CLI demo transcript (captured from an
actual `python orchestrator.py` run, see docs/cli_demo_transcript.txt)
as a terminal-style animated GIF for the README. No screen recording —
this only draws text frames with Pillow, so it's fully scriptable and
reproducible.

Usage:
    python scripts/make_demo_gif.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent.parent
TRANSCRIPT_PATH = ROOT / "docs" / "cli_demo_transcript.txt"
OUTPUT_PATH = ROOT / "docs" / "demo.gif"

FONT_PATH = "C:/Windows/Fonts/consola.ttf"
FONT_SIZE = 16
CHARS_PER_FRAME = 18
HOLD_FRAMES_AT_END = 6
FRAME_MS = 30
HOLD_FRAME_MS = 600

WIDTH = 900
HEIGHT = 560
PADDING = 16
LINE_HEIGHT = 20
MAX_VISIBLE_LINES = (HEIGHT - 2 * PADDING) // LINE_HEIGHT

BG_COLOR = (13, 17, 23)
FG_COLOR = (201, 209, 217)
PROMPT_COLOR = (88, 166, 255)
HIGHLIGHT_COLOR = (248, 81, 73)


def wrap_line(line: str, max_chars: int) -> list[str]:
    if not line:
        return [""]
    words = line.split(" ")
    wrapped, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > max_chars and current:
            wrapped.append(current)
            current = word
        else:
            current = candidate
    if current:
        wrapped.append(current)
    return wrapped


def color_for_line(line: str) -> tuple[int, int, int]:
    if line.startswith("$"):
        return PROMPT_COLOR
    if "APPROVAL REQUIRED" in line or "Severity" in line or "High" in line:
        return HIGHLIGHT_COLOR
    return FG_COLOR


def render_frame(font: ImageFont.FreeTypeFont, visible_lines: list[str]) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    y = PADDING
    for line in visible_lines:
        draw.text((PADDING, y), line, font=font, fill=color_for_line(line))
        y += LINE_HEIGHT
    return img


def main() -> None:
    raw = TRANSCRIPT_PATH.read_text(encoding="utf-8")
    session = "$ python orchestrator.py\n" + raw

    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    max_chars = (WIDTH - 2 * PADDING) // (FONT_SIZE // 2 + 1)

    all_lines: list[str] = []
    for raw_line in session.splitlines():
        all_lines.extend(wrap_line(raw_line, max_chars))
    full_text_lines = all_lines

    frames: list[Image.Image] = []
    revealed_lines: list[str] = []
    current_line = ""
    char_budget = 0

    for line in full_text_lines:
        for ch in line:
            current_line += ch
            char_budget += 1
            if char_budget >= CHARS_PER_FRAME:
                char_budget = 0
                visible = (revealed_lines + [current_line])[-MAX_VISIBLE_LINES:]
                frames.append(render_frame(font, visible))
        revealed_lines.append(current_line)
        current_line = ""

    visible = revealed_lines[-MAX_VISIBLE_LINES:]
    final_frame = render_frame(font, visible)
    frames.extend([final_frame] * HOLD_FRAMES_AT_END)

    typing_frame_count = len(frames) - HOLD_FRAMES_AT_END
    durations = [FRAME_MS] * typing_frame_count + [HOLD_FRAME_MS] * HOLD_FRAMES_AT_END
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUTPUT_PATH,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    print(f"Wrote {len(frames)} frames to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
