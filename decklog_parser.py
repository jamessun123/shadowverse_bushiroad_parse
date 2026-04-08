#!/usr/bin/env python3
"""Extract Japanese card names and card codes from Deck Log."""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from typing import Dict, List

from playwright.sync_api import sync_playwright


def card_code_from_url(url: str) -> str:
    # Example: .../BP14/bp14-p28.png -> BP14-P28
    name = url.split("/")[-1].split("?")[0]
    name = re.sub(r"\.png$", "", name, flags=re.IGNORECASE)
    # Normalize old variants like BP01_LD03 / PR_001 to BP01-LD03 / PR-001.
    return name.upper().replace("_", "-")


def resolve_non_pr_code_from_jp_name(card_name_jp: str, original_code: str) -> str:
    """
    For PR cards, JP search results often include the corresponding non-PR set code.
    Example: PR-371 + 盗賊の乱飛 -> BP14-034
    """
    search_url = (
        "https://shadowverse-evolve.com/cardlist/cardsearch/?card_name="
        + urllib.parse.quote(card_name_jp)
    )
    req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", "ignore")

    # Match common SVE card code formats.
    candidates = re.findall(r"\b[A-Z]{2,4}\d{2}[-_][A-Z]{0,3}\d{2,3}\b", html)
    seen = set()
    ordered = []
    for c in candidates:
        cu = c.upper().replace("_", "-")
        if cu in seen:
            continue
        seen.add(cu)
        ordered.append(cu)

    # User preference: choose the first BP* code from results.
    for code in ordered:
        if code.startswith("BP"):
            return code

    # Fallback: any non-PR result.
    for code in ordered:
        if not code.startswith("PR-"):
            return code
    return original_code


def build_en_cards_link(card_code: str) -> str:
    # EN site card details follow: ?cardno=BP05-LD02EN
    return "https://en.shadowverse-evolve.com/cards/?cardno=" + card_code.upper() + "EN"


def fetch_en_card_name(en_cards_link: str) -> str:
    req = urllib.request.Request(
        en_cards_link,
        headers={
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", "ignore")

    # Prefer title format: "Albert, Tempestuous Doom | CARDS | Shadowverse: Evolve"
    m = re.search(r"<title>\s*([^<]+?)\s*\|\s*CARDS\s*\|", html, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Fallback to page heading.
    m = re.search(r"<h1[^>]*>\s*([^<]+?)\s*</h1>", html, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return ""


def build_tcgplayer_link(card_name_en: str) -> str:
    query = urllib.parse.quote_plus(card_name_en)
    return (
        "https://www.tcgplayer.com/search/shadowverse-evolve/product"
        "?productLineName=shadowverse-evolve&q="
        + query
        + "&view=grid"
    )


def parse_deck_page(deck_code: str) -> List[Dict[str, str]]:
    cards: List[Dict[str, str]] = []
    seen = set()
    url = "https://decklog.bushiroad.com/view/" + deck_code

    with sync_playwright() as p:
        # Deck Log blocks strict headless in some environments; headed mode is more reliable.
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(5000)

        raw_cards = page.eval_on_selector_all(
            "img.card-view-item",
            """(imgs) => imgs.map((img) => {
                const cardName = (img.getAttribute("alt") || "").trim();
                const imgUrl = (img.getAttribute("data-src") || img.getAttribute("src") || "").trim();
                const box = img.closest("li") || img.parentElement;
                let copies = 1;
                if (box) {
                  const candidates = box.querySelectorAll(
                    "[class*='num'],[class*='count'],[class*='copy'],[class*='quantity'],strong,em,span,div"
                  );
                  for (const el of candidates) {
                    const t = (el.textContent || "").trim();
                    if (/^[0-9]{1,2}$/.test(t)) {
                      const n = parseInt(t, 10);
                      if (Number.isFinite(n) && n > 0 && n <= 20) {
                        copies = n;
                        break;
                      }
                    }
                  }
                }
                return { card_name: cardName, img_url: imgUrl, copies };
            })""",
        )

        for row in raw_cards:
            card_name = str(row.get("card_name", "")).strip()
            img_url = str(row.get("img_url", "")).strip()
            if not card_name or not img_url:
                continue
            copies = int(row.get("copies", 1) or 1)

            card_code = card_code_from_url(img_url)
            effective_code = card_code
            if card_code.startswith("PR-"):
                effective_code = resolve_non_pr_code_from_jp_name(card_name, card_code)

            en_cards_link = build_en_cards_link(effective_code)
            card_name_en = fetch_en_card_name(en_cards_link)
            key = (card_code, card_name)
            if key in seen:
                continue
            seen.add(key)

            cards.append(
                {
                    "card_code_jp": card_code,
                    "card_code_for_en_lookup": effective_code,
                    "card_name_jp": card_name,
                    "image_url": img_url,
                    "copies": copies,
                    "card_name_en": card_name_en,
                    "en_cards_link": en_cards_link,
                    "tcgplayer_link": build_tcgplayer_link(card_name_en or card_name),
                }
            )

        browser.close()

    return cards


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if len(sys.argv) < 2:
        print("Usage: python decklog_parser.py <DECK_CODE>")
        return 1

    deck_code = sys.argv[1].strip()
    if not deck_code:
        print("Deck code is required.")
        return 1

    try:
        cards = parse_deck_page(deck_code)
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 3

    result = {
        "deck_code": deck_code,
        "card_count": len(cards),
        "cards": cards,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
