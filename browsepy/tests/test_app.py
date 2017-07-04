import os
import unittest
import tempfile

import browsepy


class TestApp(unittest.TestCase):
    module = browsepy
    app = browsepy.app

    def test_config(self):
        with tempfile.NamedTemporaryFile() as f:
            f.write(b'directory_downloadable = False\n')
            f.flush()
            f.seek(0)
            os.environ['BROWSEPY_TEST_SETTINGS'] = f.name
            self.app.config['directory_downloadable'] = True
            self.app.config.from_envvar('BROWSEPY_TEST_SETTINGS')
        self.assertFalse(self.app.config['directory_downloadable'])
    