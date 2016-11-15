
import unittest
import jinja2

import browsepy.extensions


class TestHTMLCompress(unittest.TestCase):
    extension = browsepy.extensions.HTMLCompress

    def setUp(self):
        self.env = jinja2.Environment(extensions=[self.extension])

    def render(self, html, **kwargs):
        return self.env.from_string(html).render(**kwargs)

    def test_compress(self):
        html = self.render('''
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
            ''', title=42, href='index.html', css='t', a=True)
        self.assertEqual(
            html,
            '<html><head><title>42</title></head><body class="t prop">'
            '<em><b>a</b><i> b</i></em>b'
            '</body></html>'
            )

    def test_ignored(self):
        html = self.render('<script>\n <a>   <a> asdf </script>\n<br> <br>')
        self.assertEqual(html, '<script>\n <a>   <a> asdf </script><br><br>')

    def test_broken(self):
        html = self.render('<script>\n <a>   <a> asdf ')
        self.assertEqual(html, '<script>\n <a>   <a> asdf ')
