browsepy
========

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
