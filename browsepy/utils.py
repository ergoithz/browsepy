# -*- coding: UTF-8 -*-

import os
import os.path
import random
import functools

import flask


ppath = functools.partial(
    os.path.join,
    os.path.dirname(os.path.realpath(__file__)),
    )


def random_string(size, sample=tuple(map(chr, range(256)))):
    randrange = functools.partial(random.randrange, 0, len(sample))
    return ''.join(sample[randrange()] for i in range(size))


def stream_template(template_name, **context):
    '''
    Some templates can be huge, this function returns an streaming response,
    sending the content in chunks and preventing from timeout.

    :param template_name: template
    :param **context: parameters for templates.
    :yields: HTML strings
    '''
    app = flask.current_app
    app.update_template_context(context)
    template = app.jinja_env.get_template(template_name)
    stream = template.generate(context)
    return flask.Response(flask.stream_with_context(stream))
