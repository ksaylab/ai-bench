import csv
import unittest
from pathlib import Path

from aibench import cost

EP = Path(__file__).resolve().parents[1] / "episodes" / "01-buy-or-rent-gpu"


class TestCost(unittest.TestCase):
    def setUp(self):
        self.a = cost.read_assumptions(EP / "assumptions.example.csv")
        self.prices = cost.read_prices(EP / "prices.example.csv")

    def test_formula_with_example_values(self):
        card = self.prices[0]  # 1000 + PSU 500, 300 W load, 20 W idle
        # (1500 / 36) + (200 h x 70 W + 100 h x 280 W) / 1000 x BRL 1
        self.assertAlmostEqual(cost.buy_per_month(card, self.a), 1500 / 36 + (200 * 70 + 100 * 280) / 1000, 6)
        rental = self.prices[2]  # USD 0.10/h, rate 5, 20 sessions of 5 min
        self.assertAlmostEqual(cost.rent_on_demand_per_month(rental, self.a), (100 + 20 * 5 / 60) * 0.10 * 5, 6)
        self.assertAlmostEqual(cost.rent_always_on_per_month(rental, self.a), 200 * 0.10 * 5, 6)

    def test_break_even_is_the_first_whole_hour_where_buying_ties(self):
        card, rental = self.prices[0], self.prices[2]
        h = cost.break_even(card, rental, self.a)
        self.assertLessEqual(cost.buy_per_month(card, self.a, h), cost.rent_on_demand_per_month(rental, self.a, h))
        self.assertGreater(cost.buy_per_month(card, self.a, h - 1),
                           cost.rent_on_demand_per_month(rental, self.a, h - 1))

    def test_calculate_uses_the_cheapest_rental_as_reference(self):
        rows = cost.calculate(self.prices, self.a)
        self.assertEqual({r["option"] for r in rows}, {"buy", "rent_on_demand", "rent_always_on"})
        self.assertTrue(all(r["data_status"] == "EXAMPLE" for r in rows))

    def test_real_prices_still_empty_are_refused_with_the_list(self):
        with self.assertRaises(cost.CostError) as e:
            cost.read_prices(EP / "prices.csv")
        self.assertIn("rtx-3090-used", str(e.exception))
        with self.assertRaises(cost.CostError) as e:
            cost.read_assumptions(EP / "assumptions.csv")
        self.assertIn("brl_per_usd", str(e.exception))

    def test_prices_csv_has_no_made_up_values(self):
        with open(EP / "prices.csv", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                self.assertEqual((r["price_brl"], r["price_usd_per_hour"], r["status"]), ("", "", "FILL_IN"))


if __name__ == "__main__":
    unittest.main()
