.. _compat:

Compat Module
=============

.. currentmodule:: browsepy.compat

.. automodule:: browsepy.compat
  :show-inheritance:
  :members:
  :inherited-members:
  :undoc-members:
  :exclude-members: which, getdebug, deprecated,
                    FS_ENCODING, ENV_PATH, ENV_PATHEXT, TRUE_VALUES

.. attribute:: FS_ENCODING
  :annotation: = sys.getfilesystemencoding()

  Detected filesystem encoding: ie. `utf-8`.

.. attribute:: ENV_PATH
  :annotation: = ('/usr/local/bin', '/usr/bin', ... )

.. attribute:: ENV_PATHEXT
  :annotation: = ('.exe', '.bat', ... ) if os.name == 'nt' else ('',)

  List of paths where commands are located, taken and processed from
  :envvar:`PATH` environment variable. Used by :func:`which`.

.. attribute:: TRUE_VALUES
  :annotation: = frozenset({'true', 'yes', '1', 'enable', 'enabled', True, 1})

  Values which should be equivalent to True, used by :func:`getdebug`

.. autofunction:: pathconf(path)

.. autofunction:: isexec(path)

.. autofunction:: which(name, env_path=ENV_PATH, is_executable_fnc=isexec, path_join_fnc=os.path.join)

.. autofunction:: getdebug(environ=os.environ, true_values=TRUE_VALUES)

.. autofunction:: deprecated(func_or_text, environ=os.environ)

.. autofunction:: usedoc(other)

.. autofunction:: re_escape(pattern, chars="()[]{}?*+|^$\\.-#")

.. autofunction:: pathsplit(value, sep=os.pathsep)

.. autofunction:: pathparse(value, sep=os.pathsep, os_sep=os.sep)
