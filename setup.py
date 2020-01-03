"""
Browsepy package setup script.

Usage
-----

..code-block:: python

    python setup.py --help-commands

"""
import io
import re
import os
import sys
import time
import distutils

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


class AlphaVersionCommand(distutils.cmd.Command):
    """Command which update package version with alpha timestamp."""

    description = 'update package version with alpha timestamp'
    user_options = [('alpha=', None, 'alpha version (defaults to timestamp)')]

    def initialize_options(self):
        """Set alpha version."""
        self.alpha = '{:.0f}'.format(time.time())

    def finalize_options(self):
        """Check alpha version."""
        assert self.alpha, 'alpha cannot be empty'

    def iter_package_paths(self):
        for package in self.distribution.packages:
            path = '{}/__init__.py'.format(package.replace('.', os.sep))
            if os.path.isfile(path):
                yield path

    def run(self):
        """Run command."""
        for p in self.iter_package_paths():
            self.announce('Updating: {}'.format(p), level=distutils.log.INFO)
            with io.open(p, 'r+', encoding='utf8') as f:
                data = re.sub(
                    r'__version__ = \'(?P<version>[^a\']+)(a\d+)?\'',
                    lambda m: '__version__ = {!r}'.format(
                        '{}a{}'.format(m.groupdict()['version'], self.alpha)
                        ),
                    f.read(),
                    )
                f.seek(0)
                f.write(data)
                f.truncate()


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
    cmdclass={
        'alpha_version': AlphaVersionCommand,
    },
    entry_points={
        'console_scripts': (
            'browsepy=browsepy.__main__:main'
            )
        },
    package_data={  # ignored by sdist (see MANIFEST.in), used by bdist_wheel
        package: [
            '{}/{}*'.format(directory, '**/' * level)
            for directory in ('static', 'templates')
            for level in range(3)
            ]
        for package in find_packages()
        },
    python_requires='>=3.5',
    setup_requires=[
        'setuptools>36.2',
        ],
    install_requires=[
        'six',
        'flask',
        'cookieman',
        'unicategories',
        'importlib-resources ; python_version<"3.7"',
        ],
    tests_require=[
        'beautifulsoup4',
        'unittest-resources',
        'pycodestyle',
        'pydocstyle',
        'mypy',
        'radon',
        'unittest-resources[testing]',
        ],
    test_suite='browsepy',
    zip_safe=False,
    platforms='any',
    )
