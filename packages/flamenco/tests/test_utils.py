from __future__ import absolute_import

import unittest


class FrameRangeTest(unittest.TestCase):
    def test_frame_range_parse(self):
        from flamenco.utils import frame_range_parse

        self.assertEqual([], frame_range_parse(None))
        self.assertEqual([], frame_range_parse(''))
        self.assertEqual([1], frame_range_parse('1'))
        self.assertEqual([1, 2, 3], frame_range_parse('1, 2, 3'))
        self.assertEqual([1, 2, 3], frame_range_parse('1-3'))
        self.assertEqual([1, 2, 3, 4], frame_range_parse('1, 2-4'))
        self.assertEqual([1, 2, 3, 4], frame_range_parse('1,2-4'))
        self.assertEqual([0, 531443, 5315886, 9999993414, 9999993415, 9999993416],
                         frame_range_parse('0,531443,    5315886,  9999993414 - 9999993416'))

    def test_frame_range_merge(self):
        from flamenco.utils import frame_range_merge

        self.assertEqual('', frame_range_merge(None))
        self.assertEqual('', frame_range_merge([]))
        self.assertEqual('1', frame_range_merge([1]))
        self.assertEqual('18,20,21', frame_range_merge([18, 20, 21]))
        self.assertEqual('18,20,21,23-25', frame_range_merge([18, 20, 21, 23, 24, 25]))
        self.assertEqual('1-3', frame_range_merge([1, 2, 3]))
        self.assertEqual('51,66-103', frame_range_merge([51] + list(range(66, 104))))
        self.assertEqual('0,531443,5315886,9999993414-9999993416',
                         frame_range_merge(
                             [0, 531443, 5315886, 9999993414, 9999993415, 9999993416]))

    def test_iter_frame_range(self):
        from flamenco.utils import iter_frame_range

        self.assertEqual([], list(iter_frame_range(None, 1)))
        self.assertEqual(
            [
                [4, 5, 6, 7],
                [8, 9, 10, 13],
                [14, 15, 16],
            ],
            list(iter_frame_range('4-10, 13-16', 4)))
