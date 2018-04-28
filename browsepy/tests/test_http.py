
import unittest

import browsepy.http


class TestHeaders(unittest.TestCase):
    module = browsepy.http

    def test_simple(self):
        headers = self.module.Headers(
            simple_header='something',
            other_header='something else',
            )
        self.assertEqual(
            headers.get('Simple-Header'),
            'something',
            )

    def test_options(self):
        headers = self.module.Headers(
            option_header=('something', {'option': 1}),
            other_header='something else',
            )
        self.assertEqual(
            headers.get('Option-Header'),
            'something; option=1',
            )
