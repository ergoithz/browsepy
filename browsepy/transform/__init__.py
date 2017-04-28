

class StateMachine(object):
    '''
    Abstract simple character-driven state-machine for string transforms.

    Useful for implementig simple transpilations, compressors and so on.

    Important: when implementing this class, you must set the :attr:`current`
    attribute to a key defined in :attr:`jumps` dict.
    '''
    jumps = {}  # state machine jumps
    start = ''  # character which started current state
    current = ''  # initial and current state
    pending = ''  # buffer of current state data
    streaming = False  # stream mode toggle

    @property
    def nearest(self):
        try:
            options = self.jumps[self.current]
        except KeyError:
            raise KeyError(
                'Current state %r not defined in %s.jumps.'
                % (self.current, self.__class__)
                )
        offset = len(self.start)
        index = len(self.pending)
        if self.streaming:
            index -= max(map(len, options))
        key = (index, 1)
        result = (index, '', None)
        for amark, anext in options.items():
            asize = len(amark)
            aindex = self.pending.find(amark, offset, index + asize)
            if aindex > -1:
                index = aindex
                akey = (aindex, -asize)
                if akey < key:
                    key = akey
                    result = (aindex, amark, anext)
        return result

    def __init__(self, data=''):
        self.pending = data

    def __iter__(self):
        '''
        Iterate over tramsformation result chunks.

        On non-streaming mode, flush and yield it on completion.

        :yields: transformation result chunka
        :ytype: str
        '''
        index, mark, next = self.nearest
        while next is not None:
            data = self.transform(self.pending[:index], mark, next)
            self.start = mark
            self.current = next
            self.pending = self.pending[index:]
            if data:
                yield data
            index, mark, next = self.nearest
        if not self.streaming:
            data = self.transform(self.pending, mark, next)
            self.start = ''
            self.pending = ''
            if data:
                yield data

    def transform(self, data, mark, next):
        method = getattr(self, 'transform_%s' % self.current, None)
        return method(data, mark, next) if method else data

    def feed(self, data=''):
        self.streaming = True
        self.pending += data
        for i in self:
            yield i

    def finish(self, data=''):
        self.pending += data
        self.streaming = False
        for i in self:
            yield i
