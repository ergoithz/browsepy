

class StateMachine(object):
    '''
    Abstract simple character-driven state-machine for string transforms.

    Useful for implementig simple transpilations, compressors and so on.

    Important: when implementing this class, you must set the :attr:`current`
    attribute to a key defined in :attr:`jumps` dict.
    '''
    end = type('EndType', (object,), {})
    jumps = {}  # state machine jumps
    start = ''  # character which started current state
    current = ''  # initial and current state
    pending = ''  # buffer of current state data

    def __init__(self, data=''):
        self.pending = data

    def transform(self, data, mark, next):
        method = getattr(self, 'transform_%s' % self.current, None)
        return method(data, mark, next) if method else data

    def look(self, value, current, start):
        offset = len(start)
        try:
            end = len(value)
            for mark, next in self.jumps[current].items():
                index = value.find(mark, offset, end + len(mark))
                if -1 != index:
                    end = min(end, index)
                    yield index, mark, next
        except KeyError:
            raise KeyError(
                'Current state %r not defined in %s.jumps.'
                % (current, self.__class__)
                )
        yield len(value), '', None  # failing is also an option

    def flush(self):
        result = (
            self.transform(self.pending, '', self.end)
            if self.pending else
            ''
            )
        self.pending = ''
        self.start = ''
        return result

    def __iter__(self):
        while True:
            index, mark, next = min(
                self.look(self.pending, self.current, self.start),
                key=lambda x: (x[0], -len(x[1]))
                )
            if next is None:
                break
            data = self.transform(self.pending[:index], mark, next)
            self.start = mark
            self.current = next
            self.pending = self.pending[index:]
            if data:
                yield data
        data = self.flush()
        if data:
            yield data


class StreamStateMachine(StateMachine):
    streaming = False

    def feed(self, data=''):
        self.streaming = True
        self.pending += data
        for i in self:
            yield i

    def flush(self):
        if self.streaming:
            return ''
        return super(StreamStateMachine, self).flush()

    def finish(self, data=''):
        self.pending += data
        self.streaming = False
        for i in self:
            yield i
