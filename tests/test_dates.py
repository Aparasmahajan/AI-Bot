"""Dates by code (mwb/skills/dates.py), counted from Tuesday 13 October 2026 like P0-4's test meeting."""
import datetime, unittest

from mwb.skills.dates import resolve

TUE = datetime.date(2026, 10, 13)


def d(day, month=10, year=2026):
    return datetime.date(year, month, day)


class Resolve(unittest.TestCase):
    def check(self, text, want, ref=TUE):
        self.assertEqual(resolve(text, ref), want, text)

    def test_weekdays_from_a_tuesday(self):
        self.check('by Wednesday', d(14))
        self.check('Thursday', d(15))          # P0-4: the model wrote "Thursday, 14 Oct"
        self.check('by Friday', d(16))         # P0-4: the 20b got this wrong
        self.check('Monday', d(19))
        self.check('Tuesday', d(20))           # said on a Tuesday: next week's
        self.check('this Tuesday', d(13))
        self.check('next Friday', d(23))       # in the same week: the Friday after
        self.check('next Monday', d(19))

    def test_relative(self):
        self.check('today', d(13))
        self.check('EOD', d(13))
        self.check('tomorrow', d(14))
        self.check('day after tomorrow', d(15))
        self.check('in 3 days', d(16))
        self.check('in two weeks', d(27))
        self.check('end of week', d(16))
        self.check('next week', d(19))
        self.check('end of month', d(31))

    def test_written_dates(self):
        self.check('16 Oct', d(16))
        self.check('October 16th', d(16))
        self.check('16/10', d(16))
        self.check('2026-11-02', d(2, 11))
        self.check('3 Jan', d(3, 1, 2027))     # early next year, not last January
        self.check('5 Feb 2026', d(5, 2, 2026))

    def test_no_date(self):
        for text in ('no date', 'soon', 'after the demo', '', None, 'ASAP'):
            self.check(text, None)


if __name__ == '__main__':
    unittest.main()
