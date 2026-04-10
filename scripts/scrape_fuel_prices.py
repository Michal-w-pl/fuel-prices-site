from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://www.e-petrol.pl/notowania/rynek-krajowy/ceny-stacje-paliw"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "fuel_prices.json"
TIMEOUT_SECONDS = 30
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class FuelPrices:
    pb95: float
    pb98: float
    on: float
    lpg: float
    electricity: float


class ScrapeError(Exception):
    """Raised when the fuel price page cannot be parsed."""


def fetch_html(url: str) -> str:
    response = requests.get(
        url,
        timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    return response.text


def parse_decimal(value: str) -> float:
    cleaned = value.strip().replace("\xa0", " ")
    cleaned = cleaned.replace("zł", "").replace("PLN", "")
    cleaned = cleaned.replace(",", ".")
    cleaned = re.sub(r"[^0-9.]", "", cleaned)
    if not cleaned:
        raise ValueError(f"Cannot parse decimal from: {value!r}")
    return float(cleaned)


def parse_latest_prices_from_text(html: str) -> FuelPrices:
    """
    Fallback parser based on visible page text.

    Expected pattern resembles:
      Aktualizacja 2026-04-08
      Pb98 6,79
      Pb95 6,19
      ON 7,79
      LPG 3,84
    """
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    compact = re.sub(r"\s+", " ", text)

    patterns = {
        "pb98": r"Pb\s*98\s*([0-9]+,[0-9]+)",
        "pb95": r"Pb\s*95\s*([0-9]+,[0-9]+)",
        "on": r"\bON\b\s*([0-9]+,[0-9]+)",
        "lpg": r"\bLPG\b\s*([0-9]+,[0-9]+)",
    }

    values: dict[str, float] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, compact, flags=re.IGNORECASE)
        if not match:
            raise ScrapeError(f"Could not find value for {key} in page text")
        values[key] = parse_decimal(match.group(1))

    return FuelPrices(
        pb95=values["pb95"],
        pb98=values["pb98"],
        on=values["on"],
        lpg=values["lpg"],
        electricity=read_existing_electricity_price(),
    )


def find_candidate_table(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    tables = soup.find_all("table")
    for table in tables:
        text = table.get_text(" ", strip=True).lower()
        if all(token in text for token in ["pb95", "pb98", "on", "lpg"]):
            return table
    return None


def parse_latest_prices_from_table(html: str) -> FuelPrices:
    soup = BeautifulSoup(html, "html.parser")
    table = find_candidate_table(soup)
    if table is None:
        raise ScrapeError("Could not find a table with PB95/PB98/ON/LPG columns")

    rows = table.find_all("tr")
    if len(rows) < 2:
        raise ScrapeError("Fuel prices table does not contain enough rows")

    best_row_text = None
    for row in rows[1:]:
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]
        if len(cells) >= 5:
            best_row_text = cells
            break

    if best_row_text is None:
        raise ScrapeError("Could not find latest data row in fuel prices table")

    numeric_cells = [c for c in best_row_text if re.search(r"[0-9]+,[0-9]+", c)]
    if len(numeric_cells) < 4:
        raise ScrapeError("Table row does not contain four numeric price cells")

    pb98 = parse_decimal(numeric_cells[0])
    pb95 = parse_decimal(numeric_cells[1])
    on = parse_decimal(numeric_cells[2])
    lpg = parse_decimal(numeric_cells[3])

    return FuelPrices(
        pb95=pb95,
        pb98=pb98,
        on=on,
        lpg=lpg,
        electricity=read_existing_electricity_price(),
    )


def read_existing_electricity_price(default: float = 1.04) -> float:
    if not OUTPUT_PATH.exists():
        return default
    try:
        data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        return float(data.get("prices", {}).get("electricity", default))
    except (ValueError, TypeError, json.JSONDecodeError):
        return default


def scrape_prices(html: str) -> FuelPrices:
    try:
        return parse_latest_prices_from_table(html)
    except Exception:
        return parse_latest_prices_from_text(html)


def build_payload(prices: FuelPrices) -> dict:
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    return {
        "updated_at": now,
        "source": {
            "name": "e-petrol",
            "url": SOURCE_URL,
        },
        "prices": {
            "pb95": prices.pb95,
            "pb98": prices.pb98,
            "on": prices.on,
            "lpg": prices.lpg,
            "electricity": prices.electricity,
        },
        "meta": {
            "country": "Polska",
            "currency": "PLN",
            "unit_liquid": "zł/l",
            "unit_energy": "zł/kWh",
            "note": "Electricity is maintained manually in the JSON file unless you add a separate source.",
        },
    }


def save_payload(payload: dict) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    html = fetch_html(SOURCE_URL)
    prices = scrape_prices(html)
    payload = build_payload(prices)
    save_payload(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
