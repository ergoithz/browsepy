
import unittest
import jinja2

import browsepy.extensions


class TestApp(unittest.TestCase):
    extension = browsepy.extensions.HTMLCompress

    def test_compress(self):
        env = jinja2.Environment(extensions=[self.extension])
        tmpl = env.from_string('''
            <html>
              <head>
                <title>{{ title }}</title>
              </head>
              <body
               class="{{css}} prop"
               >
                <em><b>a</b>    <i> b</i></em>
                {% if a %}b{% endif %}
              </body>
            </html>
        ''')
        self.assertEqual(
            tmpl.render(title=42, href='index.html', css='t', a=True),
            '<html><head><title>42</title></head><body class="t prop">'
            '<em><b>a</b><i> b</i></em>b'
            '</body></html>'
            )
