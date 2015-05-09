browsepy
========

[![Build status](http://img.shields.io/travis/ergoithz/browsepy.svg?style=flat-square)](https://travis-ci.org/ergoithz/browsepy)
[![Test coverage](http://img.shields.io/coveralls/ergoithz/browsepy.svg?style=flat-square)](https://coveralls.io/r/ergoithz/browsepy)
[![License](http://img.shields.io/pypi/l/browsepy.svg?style=flat-square)](https://pypi.python.org/pypi/browsepy/)
[![Latest Version](http://img.shields.io/pypi/v/browsepy.svg?style=flat-square)](https://pypi.python.org/pypi/browsepy/)
[![Downloads](http://img.shields.io/pypi/dm/browsepy.svg?style=flat-square)](https://pypi.python.org/pypi/browsepy/)
![Python 2.7+, 3.3+](http://img.shields.io/badge/python-2.7+,_3.3+-FFC100.svg?style=flat-square)

Simple web file browser using flask

Features
--------

* **Simple**, like Python's SimpleHTTPServer or Apache's Directory Listing.
* **Downloadable directories**, streaming tarballs on the fly.
* **Optional remove**, which can be enabled for files under a given path.

Usage
-----

Serving $HOME/shared to all addresses 

```bash
  python -m browsepy 0.0.0.0 8080 --directory $HOME/shared
```

Showing help

```bash
  python -m browsepy --help
```

Screenshots
-----------

![Screenshot of directory with enabled remove](https://raw.githubusercontent.com/ergoithz/browsepy/master/doc/screenshot.0.3.1-0.png)
