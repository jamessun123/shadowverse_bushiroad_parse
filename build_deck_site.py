#!/usr/bin/env python3
"""Build an HTML deck viewer from parser JSON output."""

from __future__ import annotations

import html
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

USER_AGENT = "Mozilla/5.0"


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "ignore")


def url_exists(url: str) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            ctype = (resp.getheader("Content-Type") or "").lower()
            return resp.status == 200 and ("image/" in ctype or url.lower().endswith(".png"))
    except Exception:
        return False


def extract_en_image_url(card_code: str, fallback: str) -> str:
    """Build EN image URL directly from the card code (e.g., 'BP16-SL01EN')."""
    if not card_code:
        return fallback
    
    # Extract set code from card code (e.g., 'BP16-SL01EN' -> 'BP16')
    set_code = card_code.split("-")[0]
    if not set_code:
        return fallback
    
    candidate = (
        "https://en.shadowverse-evolve.com/wordpress/wp-content/images/cardlist/"
        + set_code
        + "/"
        + card_code
        + ".png"
    )
    return candidate if url_exists(candidate) else fallback


def render_html(deck_data: Dict[str, Any], cards: List[Dict[str, Any]]) -> str:
    deck_code = str(deck_data.get("deck_code", "UNKNOWN"))
    title = f"Deck {deck_code} | EN Card View"

    card_blocks: List[str] = []
    for idx, card in enumerate(cards, start=1):
        code_jp = html.escape(str(card.get("card_code_jp", "")))
        code_en = html.escape(str(card.get("card_code_for_en_lookup", code_jp)))
        copies = html.escape(str(card.get("copies", "")))
        name_jp = html.escape(str(card.get("card_name_jp", "")))
        name_en = html.escape(str(card.get("card_name_en", "")))
        img = html.escape(str(card.get("en_image_url", card.get("image_url", ""))))
        en_link = html.escape(str(card.get("en_cards_link", "")))
        tcg_link = html.escape(str(card.get("tcgplayer_link", "")))
        image_block = (
            f"""
                <button class="card-image-btn" type="button" data-full="{img}" data-alt="{name_en or name_jp}">
                  <img class="card-image" src="{img}" alt="{name_en or name_jp}" loading="lazy" />
                </button>
            """
            if img
            else """
                <div class="card-image-missing">EN image unavailable</div>
            """
        )
        card_blocks.append(
            f"""
            <article class="card">
              <div class="card-image-wrap">
                {image_block}
              </div>
              <div class="card-body">
                <div class="card-index">#{idx}</div>
                <div class="name-en">{name_en or "-"}</div>
                <div class="name-jp">{name_jp}</div>
                <div class="copies">Copies: {copies or "-"}</div>
                <div class="codes">JP: {code_jp} | EN lookup: {code_en}</div>
                <div class="links">
                  <a href="{en_link}" target="_blank" rel="noreferrer">English Card Page</a>
                  <a href="{tcg_link}" target="_blank" rel="noreferrer">TCGplayer Search</a>
                </div>
              </div>
            </article>
            """
        )

    cards_html = "\n".join(card_blocks)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #f4f6fb;
      --panel: #ffffff;
      --text: #21242a;
      --muted: #6b7380;
      --line: #dbe1ef;
      --accent: #3b82f6;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    .header {{
      background: linear-gradient(90deg, #1f2937, #111827);
      color: #fff;
      padding: 14px 20px;
      border-bottom: 3px solid #0ea5e9;
    }}
    .header h1 {{
      margin: 0;
      font-size: 20px;
      font-weight: 700;
    }}
    .header .meta {{
      margin-top: 6px;
      font-size: 13px;
      color: #d1d5db;
    }}
    .wrap {{
      max-width: 1320px;
      margin: 18px auto;
      padding: 0 14px 18px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 14px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      box-shadow: 0 1px 4px rgba(12, 18, 28, 0.08);
    }}
    .card-image-wrap {{
      background: #0f172a;
      aspect-ratio: 63 / 88;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .card-image-btn {{
      border: 0;
      padding: 0;
      margin: 0;
      width: 100%;
      height: 100%;
      cursor: zoom-in;
      background: transparent;
    }}
    .card-image {{
      width: 100%;
      height: 100%;
      object-fit: contain;
      background: #0f172a;
    }}
    .card-image-missing {{
      color: #cbd5e1;
      font-size: 12px;
      text-align: center;
      padding: 12px;
    }}
    .card-body {{
      padding: 10px;
      display: grid;
      gap: 6px;
    }}
    .card-index {{
      color: var(--muted);
      font-size: 12px;
    }}
    .name-en {{
      font-size: 14px;
      font-weight: 700;
      line-height: 1.25;
    }}
    .name-jp {{
      font-size: 13px;
      color: #334155;
      line-height: 1.25;
    }}
    .codes {{
      font-size: 12px;
      color: var(--muted);
      word-break: break-word;
    }}
    .copies {{
      font-size: 12px;
      color: #334155;
      font-weight: 600;
    }}
    .links {{
      display: grid;
      gap: 4px;
      margin-top: 2px;
    }}
    .links a {{
      color: var(--accent);
      text-decoration: none;
      font-size: 12px;
    }}
    .links a:hover {{ text-decoration: underline; }}
    .lightbox {{
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.85);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 9999;
      padding: 24px;
    }}
    .lightbox.is-open {{ display: flex; }}
    .lightbox img {{
      max-width: min(92vw, 700px);
      max-height: 92vh;
      object-fit: contain;
      border-radius: 8px;
      box-shadow: 0 12px 28px rgba(0, 0, 0, 0.35);
      background: #0f172a;
    }}
  </style>
</head>
<body>
  <header class="header">
    <h1>Deck Code: {html.escape(deck_code)}</h1>
    <div class="meta">{len(cards)} cards - English image + links view</div>
  </header>
  <main class="wrap">
    <section class="grid">
      {cards_html}
    </section>
  </main>
  <div id="lightbox" class="lightbox" aria-hidden="true">
    <img id="lightboxImage" src="" alt="" />
  </div>
  <script>
    (function () {{
      const lightbox = document.getElementById("lightbox");
      const lightboxImage = document.getElementById("lightboxImage");
      document.querySelectorAll(".card-image-btn").forEach((btn) => {{
        btn.addEventListener("click", () => {{
          const full = btn.getAttribute("data-full");
          const alt = btn.getAttribute("data-alt") || "";
          if (!full) return;
          lightboxImage.src = full;
          lightboxImage.alt = alt;
          lightbox.classList.add("is-open");
          lightbox.setAttribute("aria-hidden", "false");
        }});
      }});
      lightbox.addEventListener("click", () => {{
        lightbox.classList.remove("is-open");
        lightbox.setAttribute("aria-hidden", "true");
        lightboxImage.src = "";
      }});
      document.addEventListener("keydown", (e) => {{
        if (e.key === "Escape") {{
          lightbox.classList.remove("is-open");
          lightbox.setAttribute("aria-hidden", "true");
          lightboxImage.src = "";
        }}
      }});
    }})();
  </script>
</body>
</html>
"""


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if len(sys.argv) < 2:
        print("Usage: python build_deck_site.py <DECK_JSON_PATH> [OUTPUT_HTML_PATH]")
        return 1

    input_path = Path(sys.argv[1]).expanduser().resolve()
    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return 2

    output_path = (
        Path(sys.argv[2]).expanduser().resolve()
        if len(sys.argv) >= 3
        else input_path.with_suffix(".html")
    )

    raw = input_path.read_bytes()
    deck_data: Dict[str, Any]
    loaded = False
    for enc in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "cp932"):
        try:
            deck_data = json.loads(raw.decode(enc))
            loaded = True
            break
        except Exception:
            continue
    if not loaded:
        print(f"Could not decode JSON file: {input_path}")
        return 3

    cards: List[Dict[str, Any]] = list(deck_data.get("cards", []))
    for card in cards:
        card_code_en = str(card.get("card_code_for_en_lookup", "")).strip()
        # Append 'EN' suffix if not already present for image URL construction
        if card_code_en and not card_code_en.upper().endswith("EN"):
            card_code_en += "EN"
        # Build image URL directly from card code
        card["en_image_url"] = extract_en_image_url(card_code_en, "") if card_code_en else ""
        card_code = card.get("card_code_jp", "UNKNOWN")
        print(f"DEBUG: Card {card_code}: en_image_url = {card['en_image_url']}", file=sys.stderr)

    html_doc = render_html(deck_data, cards)
    with output_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(html_doc)

    print(f"Wrote: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
