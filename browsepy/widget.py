'''
WARNING: deprecated module.

API defined in this module has been deprecated in version 0.5 will likely be
removed at 0.6.
'''
import warnings

from markupsafe import Markup
from flask import url_for

from .compat import deprecated


warnings.warn('Deprecated module widget', category=DeprecationWarning)


class WidgetBase(object):
    _type = 'base'
    place = None

    @deprecated('Deprecated widget API')
    def __new__(cls, *args, **kwargs):
        return super(WidgetBase, cls).__new__(cls)

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def for_file(self, file):
        return self

    @classmethod
    def from_file(cls, file):
        if not hasattr(cls, '__empty__'):
            cls.__empty__ = cls()
        return cls.__empty__.for_file(file)


class LinkWidget(WidgetBase):
    _type = 'link'
    place = 'link'

    def __init__(self, text=None, css=None, icon=None):
        self.text = text
        self.css = css
        self.icon = icon
        super(LinkWidget, self).__init__()

    def for_file(self, file):
        if None in (self.text, self.icon):
            return self.__class__(
                file.name if self.text is None else self.text,
                self.css,
                self.icon if self.icon is not None else
                'dir-icon' if file.is_directory else
                'file-icon',
            )
        return self


class ButtonWidget(WidgetBase):
    _type = 'button'
    place = 'button'

    def __init__(self, html='', text='', css=''):
        self.content = Markup(html) if html else text
        self.css = css
        super(ButtonWidget, self).__init__()


class StyleWidget(WidgetBase):
    _type = 'stylesheet'
    place = 'style'

    @property
    def href(self):
        return url_for(*self.args, **self.kwargs)


class JavascriptWidget(WidgetBase):
    _type = 'script'
    place = 'javascript'

    @property
    def src(self):
        return url_for(*self.args, **self.kwargs)
