
class HTMLElement(object):
    def __init__(self, place, type, **kwargs):
        self.type = type
        self.place = place
        self.kwargs = kwargs

    @property
    def as_base(self):
        return dict(
            type=None,
            place=self.place
        )

    @property
    def as_link(self):
        dct = self.as_base
        dct.update(
            type='link',
            css=self.kwargs.get('css'),
            text=self.kwargs.get('text'),
            endpoint=self.kwargs.get('endpoint')
            )
        return dct

    @property
    def as_button(self):
        dct = self.as_link
        css = dct.get('css')
        dct.update(
            type='button',
            css='button{}{}'.format(' ' if css else '', css)
            )
        return dct

    @property
    def as_stylesheet(self):
        dct = self.as_base
        dct.update(
            type='stylesheet',
            href=self.kwargs.get('href')
        )
        return dct

    @property
    def as_javascript(self):
        dct = self.as_base
        dct.update(
            type='javascript',
            src=self.kwargs.get('src')
        )
        return dct

    @property
    def as_type(self):
        return getattr(self, 'as_{}'.format(self.type), self.as_base)
