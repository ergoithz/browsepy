browsepy
========

Simple web file browser using flask

Features
--------

* Simple and easy-to-use file browser similar to Python's SimpleHTTPServer or Apache's Directory Listing,
  showing current path on title as breadcrumb (more user-friendly that **..** inodes).
* Downloadable directories using on-the-fly streaming tarballs (minimal RAM usage, no writes to disk).
* Optional remove, can be enabled for files under a given path.

Usage
-----


    python -m browsepy --help

Screenshots
-----------

![Screenshot of directory with enabled remove](https://raw.githubusercontent.com/ergoithz/browsepy/master/doc/screenshot.0.3.1-0.png)
