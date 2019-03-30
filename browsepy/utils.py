
import os
import os.path
import random
import functools

ppath = functools.partial(
    os.path.join,
    os.path.dirname(os.path.realpath(__file__)),
    )


def random_string(size, sample=tuple(map(chr, range(256)))):
    randrange = functools.partial(random.randrange, 0, len(sample))
    return ''.join(sample[randrange()] for i in range(size))
