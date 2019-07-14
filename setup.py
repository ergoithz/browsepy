# -*- coding: utf-8 -*-

import io
import re
import os
import sys

from setuptools import setup, find_packages

with io.open('README.rst', 'rt', encoding='utf8') as f:
    readme = f.read()

with io.open('browsepy/__init__.py', 'rt', encoding='utf8') as f:
    version = re.search(r'__version__ = \'(.*?)\'', f.read()).group(1)

for debugger in ('ipdb', 'pudb', 'pdb'):
    opt = '--debug=%s' % debugger
    if opt in sys.argv:
        os.environ['UNITTEST_DEBUG'] = debugger
        sys.argv.remove(opt)

setup(
    name='browsepy',
    version=version,
    url='https://github.com/ergoithz/browsepy',
    license='MIT',
    author='Felipe A. Hernandez',
    author_email='ergoithz@gmail.com',
    description='Simple web file browser',
    long_description=readme,
    long_description_content_type='text/x-rst',
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        ],
    keywords=['web', 'file', 'browser'],
    packages=find_packages(),
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
            ],
        'browsepy.plugin.file_actions': [
            'templates/*',
            'static/*',
            ],
        },
    setup_requires=[
        'setuptools>36.2',
        ],
    install_requires=[
        'flask',
        'unicategories',
        'cookieman',
        'backports.shutil_get_terminal_size ; python_version<"3.3"',
        'scandir ; python_version<"3.5"',
        'pathlib2 ; python_version<"3.5"',
        'importlib-resources ; python_version<"3.7"',
        ],
    tests_require=[
        'beautifulsoup4',
        'unittest-resources',
        ],
    test_suite='browsepy.tests',
    test_runner='browsepy.tests.runner:DebuggerTextTestRunner',
    zip_safe=False,
    platforms='any',
    )
