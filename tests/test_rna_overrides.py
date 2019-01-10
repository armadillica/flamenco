import unittest


class RNAOverridesValidationTest(unittest.TestCase):
    def validate(self, lines):
        from flamenco.jobs import rna_overrides
        return rna_overrides.validate_rna_overrides(lines)

    def test_happy(self):
        self.assertIsNone(self.validate(['one = 1', 'two = 2']))
        self.assertIsNone(self.validate(['jemoeder = "op je hoofd"']))
        self.assertIsNone(self.validate(['']))
        self.assertIsNone(self.validate([]))

    def test_syntax_error(self):
        msg, line_num = self.validate(['one = 1', 'two = two two two'])
        self.assertIn('invalid syntax', msg)
        self.assertIn('two two two', msg)
        self.assertEqual(line_num, 2)

    def test_value_error(self):
        msg, line_num = self.validate(['one = 1', 'two = two two\0two'])
        self.assertIn('null byte', msg)
        self.assertEqual(line_num, 0)
