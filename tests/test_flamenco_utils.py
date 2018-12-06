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

    def test_frame_range_merge_blender_style(self):
        from flamenco.utils import frame_range_merge

        self.assertEqual('', frame_range_merge(None, blender_style=True))
        self.assertEqual('', frame_range_merge([], blender_style=True))
        self.assertEqual('1', frame_range_merge([1], blender_style=True))
        self.assertEqual('18,20,21', frame_range_merge([18, 20, 21], blender_style=True))
        self.assertEqual('18,20,21,23..25',
                         frame_range_merge([18, 20, 21, 23, 24, 25], blender_style=True))
        self.assertEqual('1..3', frame_range_merge([1, 2, 3], blender_style=True))
        self.assertEqual('51,66..103',
                         frame_range_merge([51] + list(range(66, 104)), blender_style=True))
        self.assertEqual('0,531443,5315886,9999993414..9999993416',
                         frame_range_merge(
                             [0, 531443, 5315886, 9999993414, 9999993415, 9999993416],
                             blender_style=True))

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

    def test_camel_case_to_lower_case_underscore(self):
        from flamenco.utils import camel_case_to_lower_case_underscore as cctlcu

        self.assertIsInstance(cctlcu('word'), str)
        self.assertIsInstance(cctlcu('word'), str)

        self.assertEqual('word', cctlcu('word'))
        self.assertEqual('word', cctlcu('word'))
        self.assertEqual('camel_case', cctlcu('CamelCase'))
        self.assertEqual('camel_case', cctlcu('camelCase'))
        self.assertEqual('camel_case_with_many_words', cctlcu('CamelCaseWithManyWords'))
        self.assertEqual('', cctlcu(''))
        self.assertIs(None, cctlcu(None))

    def test_frame_range_start_end(self):
        from flamenco.utils import frame_range_start_end

        self.assertEqual((None, None), frame_range_start_end(None))
        self.assertEqual((None, None), frame_range_start_end(''))
        self.assertEqual((1, 1), frame_range_start_end('1,1'))
        self.assertEqual((1, 10), frame_range_start_end('1,10'))
        self.assertEqual((0, 100), frame_range_start_end('0-100'))
        self.assertEqual((0, 140), frame_range_start_end('0-100, 130-140'))
        self.assertEqual((0, 100), frame_range_start_end('0-100, 4-50'))
        self.assertEqual((0, 100), frame_range_start_end('0-10, 99-100, 4-50'))
