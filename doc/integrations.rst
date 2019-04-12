.. _integrations:

Integrations
============

Browsepy is a Flask application and python module, so it could be integrated
anywhere python's `WSGI <https://www.python.org/dev/peps/pep-0333/>`_ protocol
is supported. Also, browsepy's public API could be easily reused.

Browsepy app config (available at :attr:`browsepy.app.config`) exposes the
following configuration options.

* **DIRECTORY_BASE**: anything under this directory will be served,
  defaults to current path.
* **DIRECTORY_START**: directory will be served when accessing root URL
* **DIRECTORY_REMOVE**: file removing will be available under this path,
  defaults to **None**.
* **DIRECTORY_UPLOAD**: file upload will be available under this path,
  defaults to **None**.
* **DIRECTORY_TAR_BUFFSIZE**, directory tar streaming buffer size,
  defaults to **262144** and must be multiple of 512.
* **DIRECTORY_DOWNLOADABLE** whether enable directory download or not,
  defaults to **True**.
* **USE_BINARY_MULTIPLES** whether use binary units (bi-bytes, like KiB)
  instead of common ones (bytes, like KB), defaults to **True**.
* **PLUGIN_MODULES** list of module names (absolute or relative to
  plugin_namespaces) will be loaded.
* **PLUGIN_NAMESPACES** prefixes for module names listed at PLUGIN_MODULES
  where relative PLUGIN_MODULES are searched.

Please note: After editing `PLUGIN_MODULES` value, plugin manager (available
at module :data:`browsepy.plugin_manager` and
:data:`browsepy.app.extensions['plugin_manager']`) should be reloaded using
the :meth:`browsepy.plugin_manager.reload` instance method of :meth:`browsepy.manager.PluginManager.reload` for browsepy's plugin
manager.

The other way of loading a plugin programmatically is calling
:meth:`browsepy.plugin_manager.load_plugin` instance method of
:meth:`browsepy.manager.PluginManager.load_plugin` for browsepy's plugin
manager.

.. _integrations-wsgi:

Waitress and any WSGI application
---------------------------------

Startup script running browsepy inside
`waitress <https://docs.pylonsproject.org/projects/waitress/en/latest/>`_
along with a root wsgi application.

.. code-block:: python

    #!/env/bin/python

    import os
    import os.path
    import sys

    import flask
    import werkzeug.wsgi
    import waitress

    import browsepy


    class cfg():
        base_path = os.path.abspath(os.path.dirname(__file__))
        static_path = os.path.join(base_path, 'static')
        media_path = os.path.expandvars('$HOME/media')

        stderr_path = os.path.join(base_path, 'stderr.log')
        stdout_path = os.path.join(base_path, 'stdout.log')
        pid_path = os.path.join(base_path, 'pidfile.pid')


    def setup_browsepy():
        browsepy.app.config.update(
            APPLICATION_ROOT='/browse',
            DIRECTORY_BASE=cfg.media_path,
            DIRECTORY_START=cfg.media_path,
            DIRECTORY_REMOVE=cfg.media_path,
            DIRECTORY_UPLOAD=cfg.media_path,
            PLUGIN_MODULES=['player'],
            )
        browsepy.plugin_manager.load_arguments([
            '--plugin=player',
            '--player-directory-play'
            ])
        browsepy.plugin_manager.reload()
        return browsepy.app


    def setup_app():
        app = flask.Flask(
            __name__,
            static_folder=cfg.static_path,
            static_url_path='',
            )

        @app.route('/')
        def index():
            return flask.send_from_directory(cfg.static_path, 'index.html')

        return app


    def setup_dispatcher():
        return werkzeug.wsgi.DispatcherMiddleware(
            setup_app(),
            {
                '/browse': setup_browsepy(),
                # add other wsgi apps here
                }
            )


    def main():
        sys.stderr = open(cfg.stderr_path, 'w')
        sys.stdout = open(cfg.stdout_path, 'w')
        with open(cfg.pid_path, 'w') as f:
            f.write('%d' % os.getpid())

        try:
            print('Starting server')
            waitress.serve(setup_dispatcher(), listen='127.0.0.1:8080')
        finally:
            sys.stderr.close()
            sys.stdout.close()


    if __name__ == '__main__':
        main()


.. _integrations-cherrymusic:

Cherrypy and Cherrymusic
-------------------------

Startup script running browsepy inside the `cherrypy <http://cherrypy.org/>`_
server provided by `cherrymusic <http://www.fomori.org/cherrymusic/>`_.

.. code-block:: python

    #!/env/bin/python

    import os
    import sys
    import cherrymusicserver
    import cherrypy

    from os.path import expandvars, dirname, abspath, join as joinpath
    from browsepy import app as browsepy, plugin_manager


    class HTTPHandler(cherrymusicserver.httphandler.HTTPHandler):
        def autoLoginActive(self):
            return True

    class Root(object):
        pass

    cherrymusicserver.httphandler.HTTPHandler = HTTPHandler

    base_path = abspath(dirname(__file__))
    static_path = joinpath(base_path, 'static')
    media_path = expandvars('$HOME/media')
    root_config = {
        '/': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': static_path,
            'tools.staticdir.index': 'index.html',
        }
    }
    cherrymusic_config = {
        'server.rootpath': '/player',
    }
    browsepy.config.update(
        APPLICATION_ROOT='/browse',
        DIRECTORY_BASE=media_path,
        DIRECTORY_START=media_path,
        DIRECTORY_REMOVE=media_path,
        DIRECTORY_UPLOAD=media_path,
        PLUGIN_MODULES=['player'],
    )
    plugin_manager.reload()

    if __name__ == '__main__':
        sys.stderr = open(joinpath(base_path, 'stderr.log'), 'w')
        sys.stdout = open(joinpath(base_path, 'stdout.log'), 'w')

        with open(joinpath(base_path, 'pidfile.pid'), 'w') as f:
            f.write('%d' % os.getpid())

        cherrymusicserver.setup_config(cherrymusic_config)
        cherrymusicserver.setup_services()
        cherrymusicserver.migrate_databases()
        cherrypy.tree.graft(browsepy, '/browse')
        cherrypy.tree.mount(Root(), '/', config=root_config)

        try:
            cherrymusicserver.start_server(cherrymusic_config)
        finally:
            print('Exiting...')
