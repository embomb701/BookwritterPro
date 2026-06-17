import unittest

from bookwriter.costs import Usage, CostLedger


class TestCosts(unittest.TestCase):
    def test_usage_cost_math(self):
        # Opus 4.8: $5/1M in, $25/1M out
        u = Usage(model="claude-opus-4-8", stage="write",
                  input_tokens=1_000_000, output_tokens=1_000_000)
        self.assertAlmostEqual(u.cost(), 30.0, places=4)

    def test_cache_read_is_cheap(self):
        u = Usage(model="claude-opus-4-8", stage="write", cache_read_tokens=1_000_000)
        self.assertAlmostEqual(u.cost(), 0.5, places=4)  # 0.1x of $5

    def test_cache_write_ttl(self):
        u5 = Usage(model="claude-opus-4-8", stage="write",
                   cache_creation_tokens=1_000_000, cache_ttl="5m")
        u1 = Usage(model="claude-opus-4-8", stage="write",
                   cache_creation_tokens=1_000_000, cache_ttl="1h")
        self.assertAlmostEqual(u5.cost(), 6.25, places=4)   # 1.25x
        self.assertAlmostEqual(u1.cost(), 10.0, places=4)   # 2.0x

    def test_ledger_aggregates_and_savings(self):
        led = CostLedger()
        led.add(Usage(model="claude-opus-4-8", stage="write",
                      cache_creation_tokens=1_000_000))
        led.add(Usage(model="claude-opus-4-8", stage="write",
                      cache_read_tokens=1_000_000, output_tokens=100_000))
        led.add(Usage(model="claude-haiku-4-5", stage="extract", input_tokens=500_000))
        led.add_words(5000)
        self.assertGreater(led.total_cost(), 0)
        self.assertIn("write", led.by_stage())
        self.assertIn("claude-haiku-4-5", led.by_model())
        # savings: 1M cache-read tokens on opus saved (5 - 0.5) = $4.5
        self.assertAlmostEqual(led.cache_savings(), 4.5, places=4)
        report = led.report()
        self.assertIn("1k words", report)
        self.assertIn("Prompt-cache savings", report)


if __name__ == "__main__":
    unittest.main()
