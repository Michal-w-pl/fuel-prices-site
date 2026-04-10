import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.scrape_fuel_prices import (
    FuelPrices,
    build_payload,
    parse_decimal,
    parse_latest_prices_from_text,
    read_existing_electricity_price,
    save_payload,
    scrape_prices,
)


HTML_TEXT_SAMPLE = """
<html>
  <body>
    <div>
      Średnie ceny detaliczne paliw w Polsce
      Aktualizacja 2026-04-08
      Pb98 6,79
      Pb95 6,19
      ON 7,79
      LPG 3,84
    </div>
  </body>
</html>
"""


HTML_TABLE_SAMPLE = """
<html>
  <body>
    <table>
      <tr>
        <th>Aktualizacja</th><th>Pb98</th><th>Pb95</th><th>ON</th><th>LPG</th>
      </tr>
      <tr>
        <td>2026-04-08</td><td>6,79</td><td>6,19</td><td>7,79</td><td>3,84</td>
      </tr>
    </table>
  </body>
</html>
"""


class FuelScraperTests(unittest.TestCase):
    def test_parse_decimal(self):
        self.assertEqual(parse_decimal("6,79"), 6.79)
        self.assertEqual(parse_decimal(" 3,84 zł "), 3.84)

    def test_parse_from_text(self):
        result = parse_latest_prices_from_text(HTML_TEXT_SAMPLE)
        self.assertEqual(result.pb95, 6.19)
        self.assertEqual(result.pb98, 6.79)
        self.assertEqual(result.on, 7.79)
        self.assertEqual(result.lpg, 3.84)

    def test_parse_from_table(self):
        result = scrape_prices(HTML_TABLE_SAMPLE)
        self.assertEqual(result.pb95, 6.19)
    unittest.main()
