import sys
import subprocess
from pathlib import Path

def main() -> int:
    deck_code = sys.argv[1].strip()
    output_name = sys.argv[2].strip()

    json_path = Path(output_name).with_suffix(".json")
    html_path = Path(output_name).with_suffix(".html")

    with json_path.open("w", encoding="utf-8", newline="\n") as json_file:
        result = subprocess.run(
            [sys.executable, "decklog_parser.py", deck_code],
            stdout=json_file,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return result.returncode

    result = subprocess.run(
        [sys.executable, "build_deck_site.py", str(json_path), str(html_path)],
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode

    print(f"Wrote: {json_path} -> {html_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
