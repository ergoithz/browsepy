.. _compat:

Compat Module
=============

.. currentmodule:: browsepy.compat

.. automodule:: browsepy.compat
  :show-inheritance:
  :members:
  :inherited-members:
  :undoc-members:
  :exclude-members: which, getdebug, deprecated, fsencode, fsdecode, getcwd,
                    FS_ENCODING, PY_LEGACY, ENV_PATH, TRUE_VALUES

.. attribute:: FS_ENCODING
  :annotation: = sys.getfilesystemencoding()

  Detected filesystem encoding: ie. `utf-8`.

.. attribute:: PY_LEGACY
  :annotation: = sys.version_info < (3, )

  True on Python 2, False on newer.

.. attribute:: ENV_PATH
  :annotation: = ('/usr/local/bin', '/usr/bin', ... )

.. attribute:: ENV_PATHEXT
  :annotation: = ('.exe', '.bat', ... ) if os.name == 'nt' else ('',)

  List of paths where commands are located, taken and processed from
  :envvar:`PATH` environment variable. Used by :func:`which`.

.. attribute:: TRUE_VALUES
  :annotation: = frozenset({'true', 'yes', '1', 'enable', 'enabled', True, 1})

  Values which should be equivalent to True, used by :func:`getdebug`

.. attribute:: FileNotFoundError
  :annotation: = OSError if PY_LEGACY else FileNotFoundError

  Convenience python exception type reference.

.. attribute:: range
  :annotation: = xrange if PY_LEGACY else range

  Convenience python builtin function reference.

.. attribute:: filter
  :annotation: = itertools.ifilter if PY_LEGACY else filter

  Convenience python builtin function reference.

.. attribute:: basestring
  :annotation: = basestring if PY_LEGACY else str

  Convenience python type reference.

.. attribute:: unicode
  :annotation: = unicode if PY_LEGACY else str

  Convenience python type reference.

.. attribute:: scandir
  :annotation: = scandir.scandir or os.walk

  New scandir, either from scandir module or Python3.6+ os module.

.. attribute:: walk
  :annotation: = scandir.walk or os.walk

  New walk, either from scandir module or Python3.6+ os module.

.. autofunction:: isexec(path)

.. autofunction:: which(name, env_path=ENV_PATH, is_executable_fnc=isexec, path_join_fnc=os.path.join)

.. autofunction:: getdebug(environ=os.environ, true_values=TRUE_VALUES)

.. autofunction:: deprecated(func_or_text, environ=os.environ)

.. autofunction:: usedoc(other)

.. autofunction:: fsdecode(path, os_name=os.name, fs_encoding=FS_ENCODING, errors=None)

.. autofunction:: fsencode(path, os_name=os.name, fs_encoding=FS_ENCODING, errors=None)

.. autofunction:: getcwd(fs_encoding=FS_ENCODING, cwd_fnc=os.getcwd)

.. autofunction:: re_escape(pattern, chars="()[]{}?*+|^$\\.-#")

.. autofunction:: pathsplit(value, sep=os.pathsep)

.. autofunction:: pathparse(value, sep=os.pathsep, os_sep=os.sep)
