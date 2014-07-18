#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import sys
import os

from . import app

if __name__ == '__main__':
    app.debug = '--debug' in sys.argv
    app.run(host=os.getenv('IP', '0.0.0.0'), port=os.getenv('PORT', 8080))

