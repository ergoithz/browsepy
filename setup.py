# -*- coding: utf-8 -*-
"""
browsepy
========

Simple web file browser with directory gzipped tarball download

More details on the `github page <https://github.com/ergoithz/browsepy/>`_.


Development Version
-------------------

The browsepy development version can be installed by cloning the git
repository from `github`_::

    git clone git@github.com:ergoithz/browsepy.git

.. _github: https://github.com/ergoithz/browsepy
"""
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

with open('browsepy/__meta__.py') as f:
    data = {}
    code = compile(f.read(), 'browsepy/__meta__.py', 'exec')
    exec(code, data, data)
    __app__ = data['__app__']
    __version__ = data['__version__']
    __license__ = data['__license__']

with open('README.rst') as f:
    __doc__ = f.read()

setup(
    name=__app__,
    version=__version__,
    url='https://github.com/ergoithz/browsepy',
    download_url = 'https://github.com/ergoithz/browsepy/tarball/0.3.2',
    license=__license__,
    author='Felipe A. Hernandez',
    author_email='ergoithz@gmail.com',
    description='Simple web file browser',
    long_description=__doc__,
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
    ],

    keywords = ['web', 'file', 'browser'],
    packages=['browsepy'],
    install_requires=[
        'flask',
    ],
    include_package_data=True,
    test_suite='browsepy.tests',
    zip_safe=False,
    platforms='any'
)
