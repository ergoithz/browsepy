#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import sys

from . import app

if __name__ == '__main__':
    app.debug = '--debug' in sys.argv
    app.run()

