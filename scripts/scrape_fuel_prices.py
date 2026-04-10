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
