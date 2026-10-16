"""The clean-up rules against design §9.1's table, written the way Parakeet actually punctuates."""
import tempfile, unittest
from pathlib import Path

from mwb.skills.cleanup import clean, join_pieces, load_dictionary


class DesignTable(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp()) / 'dictionary.txt'
        d.write_text('preya -> Priya\nm t m s -> MTMS\n', encoding='utf-8')
        self.dictionary = load_dictionary([d])

    def check(self, pieces, want):
        self.assertEqual(clean(pieces if isinstance(pieces, list) else [pieces], self.dictionary), want)

    def test_fillers(self):
        self.check('Um, so I think we should, uh, ship it today.', 'So I think we should ship it today.')
        self.check('Um so I think we should uh ship it today.', 'So I think we should ship it today.')
        self.check('We ship it today, um.', 'We ship it today.')

    def test_spoken_commands(self):
        self.check('Thanks, new line, regards.', 'Thanks\nRegards.')
        self.check('Thanks. New line. Regards.', 'Thanks\nRegards.')
        self.check('Bullet point, check the consumer logs.', '- Check the consumer logs')
        self.check('Two things. Bullet point check the logs. Bullet point restart the consumer.',
                   'Two things.\n- Check the logs\n- Restart the consumer')
        self.check('Hi team, new paragraph, the build is green.', 'Hi team\n\nThe build is green.')
        self.check('Is it ready question mark', 'Is it ready?')

    def test_dictionary(self):
        self.check('Ask Preya about the M T M S release.', 'Ask Priya about the MTMS release.')
        self.check('ask preya about the m t m s release', 'Ask Priya about the MTMS release')

    def test_scratch_that(self):
        self.check('Send it Friday, scratch that, Thursday.', 'Send it Thursday.')
        self.check('send it Friday scratch that Thursday', 'Send it Thursday')
        self.check('The build is green. It failed twice. Scratch that.', 'The build is green.')

    def test_stutters(self):
        self.check('I I think the the build is fine.', 'I think the build is fine.')
        self.check('I know that that is wrong.', 'I know that that is wrong.')

    def test_nothing_left(self):
        self.check('Um.', '')
        self.check(['', ' '], '')


class Joining(unittest.TestCase):
    def test_mid_sentence_pause(self):
        self.assertEqual(join_pieces(['We should ship it today.', 'And tell Priya.']),
                         'We should ship it today and tell Priya.')
        self.assertEqual(join_pieces(['Please check the logs.', 'Because the consumer stalled.']),
                         'Please check the logs because the consumer stalled.')

    def test_real_sentence_break(self):
        self.assertEqual(join_pieces(['The build is green.', 'So we ship today.']),
                         'The build is green. So we ship today.')

    def test_hyphen_cleanup(self):
        self.assertEqual(clean(['Ticket PAY‑412 is done.']), 'Ticket PAY-412 is done.')


if __name__ == '__main__':
    unittest.main()
