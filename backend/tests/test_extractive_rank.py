import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _P in (str(_ROOT), str(_ROOT / "AI pipeline" / "summarization-deadline")):
    if _P not in sys.path:
        sys.path.insert(0, _P)

from extractive_rank import RankedSentence, rank_sentences


def _page(number, text):
    return {"page": number, "text": text}


class ExtractiveRankTests(unittest.TestCase):
    def _corpus(self):
        return [
            _page(1, "Government scholarship notification for the financial year 2026 has been published."),
            _page(1, "All eligible candidates must submit the application before the last date."),
            _page(2, "Candidates will be evaluated on merit and community background."),
            _page(2, "The final list of selected candidates will be released in June."),
        ]

    def test_returns_top_k(self):
        ranked = rank_sentences(pages=self._corpus(), top_k=2)
        self.assertLessEqual(len(ranked), 2)

    def test_small_k_caps_results(self):
        corpus = [self._corpus()[0]] * 50
        ranked = rank_sentences(pages=corpus, top_k=10)
        self.assertLessEqual(len(ranked), 10)

    def test_deterministic_output(self):
        corpus = self._corpus() * 3
        first = [r.text for r in rank_sentences(pages=corpus, top_k=5)]
        second = [r.text for r in rank_sentences(pages=corpus, top_k=5)]
        self.assertEqual(first, second)

    def test_page_retained(self):
        ranked = rank_sentences(pages=self._corpus(), top_k=20)
        pages = {r.page for r in ranked}
        self.assertEqual(pages, {1, 2})
        self.assertIsInstance(ranked[0], RankedSentence)
        self.assertGreater(ranked[0].score, 0)

    def test_empty_input(self):
        self.assertEqual(rank_sentences(pages=[], top_k=5), [])
        self.assertEqual(rank_sentences(sentences=[], top_k=5), [])

    def test_stopword_only_sentences_do_not_crash(self):
        ranked = rank_sentences(
            pages=[_page(1, "the and of in for")],
            top_k=1,
        )
        self.assertEqual(len(ranked), 1)


if __name__ == "__main__":
    unittest.main()