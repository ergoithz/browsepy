"""Generic string transform module."""

import typing


NearestOptions = typing.List[typing.Tuple[str, str]]


class StateMachine:
    """
    Character-driven finite state machine.

    Useful to implement simple string transforms, transpilators,
    compressors and so on.

    Important: when implementing this class, you must set the :attr:`current`
    attribute to a key defined in :attr:`jumps` dict.
    """

    # finite state machine jumps
    jumps = {}  # type: typing.Mapping[str, typing.Mapping[str, str]]

    start = ''  # character which started current state
    current = ''  # current state (an initial value must be set)
    pending = ''  # unprocessed remaining data
    streaming = False  # streaming mode flag

    @property
    def nearest_options(self):
        # type: () -> typing.Tuple[int, NearestOptions, typing.Optional[str]]
        """
        Get both margin and jump options for current state.

        Jump option pairs are sorted by search order.

        :returns: tuple with right margin and sorted list of jump options.
        """
        cached = self.nearest_cache.get(self.current)
        if cached:
            return cached

        try:
            jumps = self.jumps[self.current]
        except KeyError:
            raise KeyError(
                'Current state %r not defined in %s.jumps.'
                % (self.current, self.__class__)
                )
        margin = max(map(len, jumps), default=0)
        options = sorted(
            jumps.items(),
            key=lambda x: (len(x[0]), x[0]),
            reverse=True,
            )
        fallback = options.pop()[1] if options and not options[-1][0] else None
        self.nearest_cache[self.current] = margin, options, fallback
        return margin, options, fallback

    @property
    def nearest(self):
        # type: () -> typing.Tuple[int, str, typing.Optional[str]]
        """
        Get the next state jump.

        The next jump is calculated looking at :attr:`current` state
        and its possible :attr:`jumps` to find the nearest and bigger
        option in :attr:`pending` data.

        If none is found, the returned next state label will be None.

        :returns: tuple with index, substring and next state label
        """
        margin, options, fallback = self.nearest_options
        offset = len(self.start)
        index = len(self.pending) - (margin if self.streaming else 0)
        result = (offset, '', fallback)
        for amark, anext in options:
            aindex = self.pending.find(amark, offset, index)
            if aindex > -1:
                index = aindex
                result = (aindex, amark, anext)
        return result

    def __init__(self, data=''):
        # type: (str) -> None
        """
        Initialize.

        :param data: content will be added to pending data
        """
        self.pending += data
        self.nearest_cache = {}

    def __iter__(self):
        # type: () -> typing.Generator[str, None, None]
        """
        Yield over result chunks, consuming :attr:`pending` data.

        On :attr:`streaming` mode, yield only finished states.

        On non :attr:`streaming` mode, yield last state's result chunk
        even if unfinished, consuming all pending data.

        :yields: transformation result chunks
        """
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
        # type: (str, str, typing.Optional[str]) -> str
        """
        Apply the appropriate transformation method.

        It is expected transformation logic makes use of :attr:`start`,
        :attr:`current` and :attr:`streaming` instance attributes to
        better know the state is being left.

        :param data: string to transform (includes start)
        :param mark: string producing the new state jump
        :param next: state is about to star, None on finish
        :returns: transformed data
        """
        method = getattr(self, 'transform_%s' % self.current, None)
        return method(data, mark, next) if method else data

    def feed(self, data=''):
        # type: (str) -> typing.Generator[str, None, None]
        """
        Add input data and yield partial output results.

        :yields: result chunks
        """
        self.streaming = True
        self.pending += data
        for i in self:
            yield i

    def finish(self, data=''):
        # type: (str) -> typing.Generator[str, None, None]
        """
        Add input data, end processing and yield all remaining output.

        :yields: result chunks
        """
        self.streaming = False
        self.pending += data
        for i in self:
            yield i
