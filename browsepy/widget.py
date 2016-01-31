
from markupsafe import Markup
from flask import url_for

class WidgetBase(object):
    place = None
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


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