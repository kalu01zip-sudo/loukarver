import unittest
import sys
import os

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.streak_algo import calculate_streak, is_at_risk

class TestStreakAlgo(unittest.TestCase):

    def test_normal_streak(self):
        dates = {"2026-06-12", "2026-06-13", "2026-06-14"}
        streak = calculate_streak(dates, "2026-06-14")
        self.assertEqual(streak, 3)

    def test_lenient_start(self):
        # Today is the 14th, but not completed yet. Yesterday was.
        dates = {"2026-06-12", "2026-06-13"}
        streak = calculate_streak(dates, "2026-06-14")
        self.assertEqual(streak, 2)

    def test_broken_streak(self):
        # Gap on the 13th
        dates = {"2026-06-11", "2026-06-12", "2026-06-14"}
        streak = calculate_streak(dates, "2026-06-14")
        self.assertEqual(streak, 1)

    def test_zero_streak(self):
        dates = {"2026-06-10", "2026-06-11"}
        streak = calculate_streak(dates, "2026-06-14")
        self.assertEqual(streak, 0)
        
    def test_streak_of_one(self):
        dates = {"2026-06-14"}
        streak = calculate_streak(dates, "2026-06-14")
        self.assertEqual(streak, 1)
        
    def test_is_at_risk_true(self):
        dates = {"2026-06-13"}
        self.assertTrue(is_at_risk(dates, "2026-06-14", 18))
        self.assertTrue(is_at_risk(dates, "2026-06-14", 23))

    def test_is_at_risk_false_early(self):
        dates = {"2026-06-13"}
        self.assertFalse(is_at_risk(dates, "2026-06-14", 17))
        
    def test_is_at_risk_false_completed_today(self):
        dates = {"2026-06-13", "2026-06-14"}
        self.assertFalse(is_at_risk(dates, "2026-06-14", 19))
        
    def test_is_at_risk_false_missed_yesterday(self):
        dates = {"2026-06-12"}
        self.assertFalse(is_at_risk(dates, "2026-06-14", 19))

if __name__ == '__main__':
    unittest.main()
