#!/usr/bin/env python3
"""Extract Japanese card names and card codes from Deck Log."""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
import csv
from typing import Dict, List
from pathlib import Path
import requests

# Load card code mappings
mappings = {}
bp_mappings: Dict[str, str] = {}

def debug(message: str) -> None:
    print(f"DEBUG: {message}", file=sys.stderr)

def load_bp_mappings():
    """Load card code rewrite rules from BP09.csv and BP16.csv."""
    global bp_mappings
    if bp_mappings:
        return

    for filename in ("BP09.csv", "BP16.csv"):
        csv_path = Path(__file__).parent / filename
        if not csv_path.exists():
            continue

        try:
            with csv_path.open("r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                for row in reader:
                    if not row:
                        continue
                    if row[0].strip().lower() == "card number":
                        for cell in row[1:]:
                            if not cell:
                                continue
                            cell_text = cell.strip()
                            if "/" not in cell_text:
                                continue
                            parts = [part.strip() for part in cell_text.split("/", 1)]
                            if len(parts) != 2:
                                continue
                            jp_code, en_code = parts
                            if en_code.upper().endswith("EN"):
                                en_code = en_code[:-2].strip()
                            bp_mappings[jp_code] = en_code
                        break
        except Exception as e:
            print(f"Error loading {filename} mappings: {e}", file=sys.stderr)


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


def fetch_en_card_info(en_cards_link: str) -> tuple[str, bool]:
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
    name = m.group(1).strip() if m else ""

    if not name:
        m = re.search(r"<h1[^>]*>\s*([^<]+?)\s*</h1>", html, flags=re.IGNORECASE)
        if m:
            name = m.group(1).strip()

    # Determine whether the English card is evolved.
    card_type = ""
    m = re.search(
        r"Card Type\s*(?:</[^>]+>\s*)?<[^>]*>\s*([^<]+)",
        html,
        flags=re.IGNORECASE,
    )
    if not m:
        m = re.search(r"Card Type\s*[:\-]?\s*([^<\n\r]+)", html, flags=re.IGNORECASE)
    if m:
        card_type = m.group(1).strip()

    is_evolved = "/ evolved" in card_type.lower()
    return name, is_evolved


def build_tcgplayer_link(card_name_en: str) -> str:
    query = urllib.parse.quote_plus(card_name_en)
    return (
        "https://www.tcgplayer.com/search/shadowverse-evolve/product"
        "?productLineName=shadowverse-evolve&q="
        + query
        + "&view=grid"
    )


def build_jp_cards_link(card_code: str) -> str:
    return "https://shadowverse-evolve.com/cards/?cardno=" + card_code.upper()


def fetch_jp_card_is_evolved(card_code: str) -> bool:
    jp_cards_link = build_jp_cards_link(card_code)
    try:
        req = urllib.request.Request(
            jp_cards_link,
            headers={
                "User-Agent": "Mozilla/5.0",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", "ignore")
    except Exception as e:
        debug(f"Failed to fetch JP evolved status for {card_code}: {e}")
        return False

    card_type = ""
    m = re.search(
        r"カード種類\s*(?:</[^>]+>\s*)?<[^>]*>\s*([^<]+)",
        html,
        flags=re.IGNORECASE,
    )
    if not m:
        m = re.search(r"カード種類\s*[:\-]?\s*([^<\n\r]+)", html, flags=re.IGNORECASE)
    if m:
        card_type = m.group(1).strip()

    is_evolved = "エボルヴ" in card_type
    return is_evolved


def get_correct_en_code(card_code: str) -> str:
    """Look up the correct EN card code from the mappings."""
    return bp_mappings.get(card_code, "") if card_code.startswith("BP") else mappings.get(card_code, "")


def parse_deck_page(deck_code: str) -> List[Dict[str, str]]:
    cards: List[Dict[str, str]] = []
    seen = set()

    session = requests.Session()

    url = f"https://decklog.bushiroad.com/system/app/api/view/{deck_code}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"https://decklog.bushiroad.com/view/{deck_code}",
        "Origin": "https://decklog.bushiroad.com",
    }

    # IMPORTANT: must include session cookie
    cookies = {
        "CAKEPHP": "4s29poomsgjh9biork06v17a5r"
    }

    res = session.post(
        url,
        headers=headers,
        cookies=cookies,
        data="",  # Content-Length: 0
        timeout=30
    )

    res.raise_for_status()

    data = res.json()

    main_list = data.get("list", [])
    sub_list = data.get("sub_list", [])

    items = []
    if isinstance(main_list, list):
        items.extend(main_list)
    if isinstance(sub_list, list):
        items.extend(sub_list)

    for item in items:
        card_code = item.get("card_number", "").strip()
        copies = int(item.get("num", 1))
        card_name_jp = item.get("name", "").strip()

        if not card_code:
            continue

        # Normalize image URL
        img_path = item.get("img", "").strip()
        img_url = f"https://decklog.bushiroad.com/static/img/card/{img_path}" if img_path else ""

        # Prevent duplicates (same card entry)
        key = (card_code, img_url)
        if key in seen:
            continue
        seen.add(key)

        # EN lookup logic (kept from your original pipeline)
        effective_code = card_code

        # Resolve PR cards to their non-PR equivalents using Japanese card name
        if card_code.startswith("PR-") and card_name_jp:
            effective_code = resolve_non_pr_code_from_jp_name(card_name_jp, card_code)

        correct_en_code = get_correct_en_code(effective_code)
        en_lookup_code = correct_en_code if correct_en_code else effective_code

        en_cards_link = build_en_cards_link(en_lookup_code)
        card_name_en = ""
        is_evolved = False
        try:
            card_name_en, is_evolved = fetch_en_card_info(en_cards_link)
        except Exception as e:
            debug(f"Failed to fetch EN card info for {en_lookup_code}: {e}")

        if not is_evolved and card_code.startswith("PR-"):
            is_evolved = fetch_jp_card_is_evolved(card_code)
        if is_evolved and card_name_en and not card_name_en.endswith(" (Evolved)"):
            card_name_en = f"{card_name_en} (Evolved)"

        cards.append({
            "card_code_jp": card_code,
            "card_code_for_en_lookup": en_lookup_code,
            "card_name_jp": card_name_jp,
            "image_url": img_url,
            "copies": copies,
            "card_name_en": card_name_en,
            "en_cards_link": en_cards_link,
            "tcgplayer_link": build_tcgplayer_link(card_name_en or card_code),
        })

    return cards


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    load_bp_mappings()

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
