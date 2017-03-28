
class StateMachine(object):
    '''
    Abstract simple character-driven state-machine with result transformations.

    Useful for implementig simple parsers.
    '''
    jumps = {}  # state machine jumps
    start = ''  # character which started current state
    current = ''  # initial and current state
    pending = ''  # buffer of current state data

    def transform(self, data, current, start, partial=False):
        method = getattr(self, 'transform_%s' % current, None)
        return method(data, current, start, partial=False) if method else data

    def look(self, value, current, start):
        offset = len(start)
        for mark, next in self.jumps[current].items():
            index = value.find(mark, offset)
            if -1 != index:
                yield index, mark, next
        yield len(value), '', None  # failing is also an option

    def finalize(self):
        if self.pending:
            yield self.transform(self.pending, self.current, self.start, True)
        self.pending = ''
        self.current = ''

    def __iter__(self):
        while True:
            index, mark, next = min(
                self.look(self.pending, self.current, self.start),
                key=lambda x: (x[0], -len(x[1]))
                )
            if next is None:
                break
            data = self.transform(
                self.pending[:index],
                self.current,
                self.start
                )
            self.start = mark
            self.current = next
            self.pending = self.pending[index:]
            yield data


class BlobTransform(StateMachine):
    jumps = {  # state machine jumps
        'escape': {
            '': 'literal',
            },
        'lit': {
            '\\': 'escape',
            }
        }
