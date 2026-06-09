#!/usr/bin/env python3
"""
LeetCode Algorithm TOML → JSON Parser

Reads .toml algorithm definitions from public/algos/ and outputs
JSON files consumable by the AlgoVisualizer frontend.

Usage:
    python scripts/parse_algo.py                    # parse all .toml files
    python scripts/parse_algo.py two-sum            # parse specific algorithm
    python scripts/parse_algo.py --watch            # watch mode (requires watchdog)
"""

import json
import os
import sys
import glob
from pathlib import Path
import html as html_mod

from pygments import lex
from pygments.lexers import PythonLexer
from pygments.token import Token

# Ensure UTF-8 output on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ─── Pygments Syntax Highlighting ────────────────────────────────────────────

LEXER = PythonLexer()

_TOKEN_CLASS_MAP = [
    (Token.Keyword, "tokenKeyword"),
    (Token.Keyword.Constant, "tokenKeyword"),
    (Token.Keyword.Declaration, "tokenKeyword"),
    (Token.Keyword.Namespace, "tokenKeyword"),
    (Token.Keyword.Reserved, "tokenKeyword"),
    (Token.Keyword.Type, "tokenKeyword"),
    (Token.Name.Builtin, "tokenBuiltin"),
    (Token.Name.Builtin.Pseudo, "tokenBuiltin"),
    (Token.Name.Decorator, "tokenDecorator"),
    (Token.Name.Function, "tokenFunction"),
    (Token.Name.Class, "tokenFunction"),
    (Token.String, "tokenString"),
    (Token.String.Doc, "tokenString"),
    (Token.Comment, "tokenComment"),
    (Token.Comment.Special, "tokenComment"),
    (Token.Number, "tokenNumber"),
    (Token.Name.Exception, "tokenKeyword"),
]


def _get_token_class(ttype: Token) -> str | None:
    """Map Pygments token type to CSS class name."""
    for token_type, css_class in _TOKEN_CLASS_MAP:
        if ttype in token_type:
            return css_class
    return None


def highlight_code_lines(code: str) -> list[str]:
    """Highlight Python code via Pygments, return one HTML string per line."""
    tokens = list(LEXER.get_tokens(code))
    lines: list[str] = []
    current_parts: list[str] = []

    for ttype, value in tokens:
        parts = value.split("\n")
        for idx, part in enumerate(parts):
            if idx > 0:
                # flush current line
                lines.append("".join(current_parts))
                current_parts = []
            if part:
                cls = _get_token_class(ttype)
                escaped = html_mod.escape(part)
                if cls:
                    current_parts.append(f'<span class="{cls}">{escaped}</span>')
                else:
                    current_parts.append(escaped)

    if current_parts:
        lines.append("".join(current_parts))
    elif code.endswith("\n"):
        lines.append("")

    # Normalise: if the frontend expects exactly N lines matching split("\n")
    # Pad missing trailing empty lines
    expected = len(code.split("\n"))
    while len(lines) < expected:
        lines.append("")

    return lines

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        print("ERROR: No TOML parser found. Install tomli: pip install tomli")
        sys.exit(1)


ALGOS_DIR = Path(__file__).resolve().parent.parent / "public" / "algos"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "src" / "modules" / "algorithm" / "data"


def parse_toml(filepath: Path) -> dict:
    """Parse a single .toml file and return structured algorithm data."""
    with open(filepath, "rb") as f:
        raw = tomllib.load(f)

    algo = raw["algorithm"]
    steps = algo.pop("steps", [])
    summary = algo.pop("summary", {})

    # Validate required fields
    assert "id" in algo, f"Missing 'algorithm.id' in {filepath.name}"
    assert steps, f"No steps defined in {filepath.name}"

    # Build clean output
    output = {
        **algo,
        "steps": [
            {
                "id": s.get("id", idx),
                "title": s["title"],
                "titleEn": s.get("titleEn", ""),
                "code": s["code"],
                "codeHtml": highlight_code_lines(s["code"]),
                "explanation": s["explanation"],
                "visualizationType": s.get("visualizationType", "code-only"),
                "visualizationData": s.get("visualizationData", {}),
            }
            for idx, s in enumerate(steps)
        ],
        "summary": {
            "timeComplexity": summary.get("timeComplexity", ""),
            "spaceComplexity": summary.get("spaceComplexity", ""),
            "approach": summary.get("approach", ""),
            "keyInsight": summary.get("keyInsight", ""),
        },
    }

    return output


def write_json(data: dict, filename: str) -> Path:
    """Write parsed data as JSON."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    outpath = OUTPUT_DIR / filename.replace(".toml", ".json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  + {outpath.relative_to(OUTPUT_DIR.parent.parent)}")
    return outpath


def parse_all(target: str | None = None) -> list[Path]:
    """Parse all or specific algorithm TOML files."""
    pattern = f"*{target}*" if target else "*.toml"
    files = sorted(glob.glob(str(ALGOS_DIR / pattern)))

    if not files:
        print(f"No .toml files found matching '{target or '*.toml'}' in {ALGOS_DIR}")
        return []

    outputs = []
    for fpath in files:
        f = Path(fpath)
        print(f"Parsing {f.name}...")
        try:
            data = parse_toml(f)
            out = write_json(data, f.name)
            outputs.append(out)
        except Exception as e:
            print(f"  x Error: {e}")

    # Write index.json for frontend discovery
    index = []
    for out in outputs:
        with open(out, "r", encoding="utf-8") as f:
            data = json.load(f)
        index.append({
            "id": data["id"],
            "title": data["title"],
            "titleEn": data.get("titleEn", ""),
            "difficulty": data.get("difficulty", "medium"),
            "tags": data.get("tags", []),
            "dataFile": out.name,
        })

    # Sort by order
    index.sort(key=lambda x: (["easy", "medium", "hard"].index(x["difficulty"]) if x["difficulty"] in ["easy", "medium", "hard"] else 99, x["id"]))

    index_path = OUTPUT_DIR / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"\nIndex written: {index_path.relative_to(OUTPUT_DIR.parent.parent)} ({len(index)} algorithms)")

    return outputs


def watch_mode():
    """Watch algos directory for changes and re-parse."""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        print("watch mode requires watchdog: pip install watchdog")
        sys.exit(1)

    class AlgoHandler(FileSystemEventHandler):
        def on_modified(self, event):
            if event.src_path.endswith(".toml"):
                print(f"\nChange detected: {Path(event.src_path).name}")
                parse_all()

        def on_created(self, event):
            if event.src_path.endswith(".toml"):
                print(f"\nNew file: {Path(event.src_path).name}")
                parse_all()

    print(f"Watching {ALGOS_DIR} for changes...")
    event_handler = AlgoHandler()
    observer = Observer()
    observer.schedule(event_handler, str(ALGOS_DIR), recursive=False)
    observer.start()

    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--watch" in args:
        parse_all()
        watch_mode()
    elif args and args[0] != "--watch":
        parse_all(target=args[0])
    else:
        parse_all()
