
from markupsafe import Markup
from flask import url_for

class WidgetBase(object):
    place = None
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
                ('dir-icon' if file.is_directory else 'file-icon') if self.icon is None else self.icon,
            )
        return self


class ButtonWidget(WidgetBase):
    place = 'button'
    def __init__(self, html='', text='', css=''):
        self.content = Markup(html) if html else text
        self.css = css
        super(ButtonWidget, self).__init__()


class StyleWidget(WidgetBase):
    place = 'style'

    @property
    def href(self):
        return url_for(*self.args, **self.kwargs)


class JavascriptWidget(WidgetBase):
    place = 'javascript'

    @property
    def src(self):
        return url_for(*self.args, **self.kwargs)