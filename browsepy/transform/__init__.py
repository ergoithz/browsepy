

class StateMachine(object):
    '''
    Abstract character-driven finite state machine implementation, used to
    chop down and transform strings.

    Useful for implementig simple transpilators, compressors and so on.

    Important: when implementing this class, you must set the :attr:`current`
    attribute to a key defined in :attr:`jumps` dict.
    '''
    jumps = {}  # finite state machine jumps
    start = ''  # character which started current state
    current = ''  # current state (an initial value must be set)
    pending = ''  # unprocessed remaining data
    streaming = False  # stream mode toggle

    @property
    def nearest(self):
        '''
        Get the next state jump.

        The next jump is calculated looking at :attr:`current` state
        and its possible :attr:`jumps` to find the nearest and bigger
        option in :attr:`pending` data.

        If none is found, the returned next state label will be None.

        :returns: tuple with index, substring and next state label
        :rtype: tuple
        '''
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
        '''
        :param data: content will be added to pending data
        :type data: str
        '''
        self.pending += data

    def __iter__(self):
        '''
        Yield over result chunks, consuming :attr:`pending` data.

        On :attr:`streaming` mode, yield only finished states.

        On non :attr:`streaming` mode, yield last state's result chunk
        even if unfinished, consuming all pending data.

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
        '''
        Apply the appropriate transformation function on current state data,
        which is supposed to end at this point.

        It is expected transformation logic makes use of :attr:`start`,
        :attr:`current` and :attr:`streaming` instance attributes to
        bettee know the state is being left.

        :param data: string to transform (includes start)
        :type data: str
        :param mark: string producing the new state jump
        :type mark: str
        :param next: state is about to star, None on finish
        :type next: str or None

        :returns: transformed data
        :rtype: str
        '''
        method = getattr(self, 'transform_%s' % self.current, None)
        return method(data, mark, next) if method else data

    def feed(self, data=''):
        '''
        Optionally add pending data, switch into streaming mode, and yield
        result chunks.

        :yields: result chunks
        :ytype: str
        '''
        self.streaming = True
        self.pending += data
        for i in self:
            yield i

    def finish(self, data=''):
        '''
        Optionally add pending data, turn off streaming mode, and yield
        result chunks, which implies all pending data will be consumed.

        :yields: result chunks
        :ytype: str
        '''
        self.pending += data
        self.streaming = False
        for i in self:
            yield i
