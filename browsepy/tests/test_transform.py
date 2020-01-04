
import re
import unittest
import warnings

import browsepy.transform
import browsepy.transform.glob
import browsepy.transform.template


class TestStateMachine(unittest.TestCase):
    module = browsepy.transform

    def test_nearest_error(self):
        m = self.module.StateMachine()
        self.assertRaises(KeyError, lambda: m.nearest)


class TestGlob(unittest.TestCase):
    module = browsepy.transform.glob
    translate = staticmethod(module.translate)

    def assertSubclass(self, cls, base):
        self.assertIn(base, cls.mro())

    def test_glob(self):
        translations = [
            ('/a', r'^/a(/|$)'),
            ('a', r'/a(/|$)'),
            ('/a*', r'^/a[^/]*(/|$)'),
            ('/a**', r'^/a.*(/|$)'),
            ('a?', r'/a[^/](/|$)'),
            ('/a{b,c}', r'^/a(b|c)(/|$)'),
            ('/a[a,b]', r'^/a[a,b](/|$)'),
            ('/a[!b]', r'^/a[^b](/|$)'),
            ('/a[!/]', r'^/a[^/](/|$)'),
            ('/a[]]', r'^/a[\]](/|$)'),
            ('/a\0', r'^/a\u0000(/|$)'),
            ('/a\\*', r'^/a\*(/|$)'),
            ('a{,.{txt,py[!od]}}', r'/a(|\.(txt|py[^od]))(/|$)'),
            ('a,a', r'/a,a(/|$)'),
            ]
        self.assertListEqual(
            [self.translate(g, sep='/') for g, r in translations],
            [r for g, r in translations]
            )

        translations = [
            ('/a', r'^\\a(\\|$)'),
            ('a', r'\\a(\\|$)'),
            ('/a*', r'^\\a[^\\]*(\\|$)'),
            ('/a**', r'^\\a.*(\\|$)'),
            ('a?', r'\\a[^\\](\\|$)'),
            ('/a{b,c}', r'^\\a(b|c)(\\|$)'),
            ('/a[a,b]', r'^\\a[a,b](\\|$)'),
            ('/a[!b]', r'^\\a[^b](\\|$)'),
            ('/a[!/]', r'^\\a[^\\](\\|$)'),
            ('/a[]]', r'^\\a[\]](\\|$)'),
            ('/a\\*', r'^\\a\*(\\|$)'),
            ]
        self.assertListEqual(
            [self.translate(g, sep='\\') for g, r in translations],
            [r for g, r in translations]
            )

    def test_unicode(self):
        tests = [
            ('/[[:alpha:][:digit:]]', (
                '/a',
                '/ñ',
                '/1',
                '/à',
                ), (
                '/_',
                )),
            ('/[[:alpha:]0-5]', (
                '/a',
                '/á',
                ), (
                '/6',
                '/_',
                )),
            ]
        for pattern, matching, nonmatching in tests:
            pattern = re.compile(self.translate(pattern, sep='/'))
            for test in matching:
                self.assertTrue(pattern.match(test))
            for test in nonmatching:
                self.assertFalse(pattern.match(test))

    def test_unsupported(self):
        translations = [
            ('[[.a-acute.]]a', '/.a(/|$)'),
            ('/[[=a=]]a', '^/.a(/|$)'),
            ('/[[=a=]\\d]a', '^/.a(/|$)'),
            ('[[:non-existent-class:]]a', '/.a(/|$)'),
            ]
        for source, result in translations:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                self.assertEqual(self.translate(source, sep='/'), result)
                self.assertSubclass(w[-1].category, Warning)


class TestXML(unittest.TestCase):
    module = browsepy.transform.template

    @classmethod
    def translate(cls, data):
        return ''.join(cls.module.SGMLMinifyContext(data))

    def test_minify(self):
        a = '''
            <root
                attr="true">with some text content </root>
            '''
        b = '<root attr="true">with some text content </root>'
        self.assertEqual(self.translate(a), b)


class TestJS(unittest.TestCase):
    module = browsepy.transform.template

    @classmethod
    def translate(cls, data):
        return ''.join(cls.module.JSMinifyContext(data))

    def test_minify(self):
        a = r'''
            function    a() {
                return 1 + 7 /2
            }
            var a = {b: ' this\' '}; // line comment
            /*
             * multiline comment
             */
            window
            .location
            .href =      '#top';
            [1,2,3][0]
            '''
        b = (
            'function a(){return 1+7/2}var a={b:\' this\\\' \'};'
            'window.location.href=\'#top\';'
            '[1,2,3][0]'
            )
        self.assertEqual(self.translate(a), b)
