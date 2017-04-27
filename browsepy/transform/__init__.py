

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

    def __init__(self, data=''):
        self.pending = data

    def transform(self, data, mark, next):
        method = getattr(self, 'transform_%s' % self.current, None)
        return method(data, mark, next) if method else data

    def look(self, value, current, start):
        offset = len(start)
        try:
            index = len(value)
            if self.streaming:
                index -= max(map(len, self.jumps))
            size = 0
            mark = ''
            next = None
            for amark, anext in self.jumps[current].items():
                asize = len(amark)
                aindex = value.find(amark, offset, index + asize)
                if (
                  aindex == -1 or
                  aindex > index or
                  aindex == index and asize < size):
                    continue
                index = aindex
                size = asize
                mark = amark
                next = anext
        except KeyError:
            raise KeyError(
                'Current state %r not defined in %s.jumps.'
                % (current, self.__class__)
                )
        return index, mark, next

    def __iter__(self):
        '''
        Iterate over tramsformation result chunks.

        On non-streaming mode, flush and yield it on completion.

        :yields: transformation result chunka
        :ytype: str
        '''
        while True:
            index, mark, next = self.look(
                self.pending, self.current, self.start)
            if next is None:
                break
            data = self.transform(self.pending[:index], mark, next)
            self.start = mark
            self.current = next
            self.pending = self.pending[index:]
            if data:
                yield data
        if not self.streaming:
            data = (
                self.transform(self.pending, '', None)
                if self.pending else
                ''
                )
            self.pending = ''
            self.start = ''
            yield data

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
