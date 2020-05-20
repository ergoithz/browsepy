
import flask


def clear_localstack(stack):
    '''
    Clear given werkzeug LocalStack instance.

    :param ctx: local stack instance
    :type ctx: werkzeug.local.LocalStack
    '''
    while stack.pop():
        pass


def clear_flask_context():
    '''
    Clear flask current_app and request globals.

    When using :meth:`flask.Flask.test_client`, even as context manager,
    the flask's globals :attr:`flask.current_app` and :attr:`flask.request`
    are left dirty, so testing code relying on them will probably fail.

    This function clean said globals, and should be called after testing
    with :meth:`flask.Flask.test_client`.
    '''
    clear_localstack(flask._app_ctx_stack)
    clear_localstack(flask._request_ctx_stack)
