# -*- coding: utf-8 -*-
"""
browsepy
========

Simple web file browser with directory gzipped tarball download, file upload,
removal and plugins.

More details on project's README and
`github page <https://github.com/ergoithz/browsepy/>`_.


Development Version
-------------------

The browsepy development version can be installed by cloning the git
repository from `github`_::

    git clone git@github.com:ergoithz/browsepy.git

.. _github: https://github.com/ergoithz/browsepy

License
-------
MIT (see LICENSE file).
"""

import os
import os.path
import sys

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

sys_path = sys.path[:]
sys.path[:] = (os.path.abspath('browsepy'),)
__import__('__meta__')
sys.path[:] = sys_path

meta = sys.modules['__meta__']
meta_app = meta.__app__
meta_version = meta.__version__
meta_license = meta.__license__

with open('README.rst') as f:
    meta_doc = f.read()

extra_requires = []

if not hasattr(os, 'scandir') or 'bdist_wheel' in sys.argv:
    extra_requires.append('scandir')

for debugger in ('ipdb', 'pudb', 'pdb'):
    opt = '--debug=%s' % debugger
    if opt in sys.argv:
        os.environ['UNITTEST_DEBUG'] = debugger
        sys.argv.remove(opt)

setup(
    name=meta_app,
    version=meta_version,
    url='https://github.com/ergoithz/browsepy',
    download_url='https://github.com/ergoithz/browsepy/archive/0.5.2.tar.gz',
    license=meta_license,
    author='Felipe A. Hernandez',
    author_email='ergoithz@gmail.com',
    description='Simple web file browser',
    long_description=meta_doc,
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
    ],
    keywords=['web', 'file', 'browser'],
    packages=[
        'browsepy',
        'browsepy.tests',
        'browsepy.tests.deprecated',
        'browsepy.tests.deprecated.plugin',
        'browsepy.plugin',
        'browsepy.plugin.player',
        ],
    entry_points={
        'console_scripts': (
            'browsepy=browsepy.__main__:main'
        )
    },
    package_data={  # ignored by sdist (see MANIFEST.in), used by bdist_wheel
        'browsepy': [
            'templates/*',
            'static/fonts/*',
            'static/*.*',  # do not capture directories
        ],
        'browsepy.plugin.player': [
            'templates/*',
            'static/*/*',
        ]},
    install_requires=['flask'] + extra_requires,
    test_suite='browsepy.tests',
    test_runner='browsepy.tests.runner:DebuggerTextTestRunner',
    zip_safe=False,
    platforms='any'
)
