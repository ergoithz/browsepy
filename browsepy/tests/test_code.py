
import re
import os
import unittest

import browsepy.compat as compat

import unittest_resources.testing as base


@unittest.skipIf(
    os.getenv('NOCODECHECKS') in compat.TRUE_VALUES,
    'env NOCODECHECKS set to true.'
    )
class Rules:
    """Browsepy module mixin."""

    meta_module = 'browsepy'
    meta_module_pattern = re.compile(r'^([^t]*|t(?!ests?))+$')
    meta_resource_pattern = re.compile(r'^([^t]*|t(?!ests?))+\.py$')


class TypingTestCase(Rules, base.TypingTestCase):
    """TestCase checking :module:`mypy`."""


class CodeStyleTestCase(Rules, base.CodeStyleTestCase):
    """TestCase checking :module:`pycodestyle`."""


class DocStyleTestCase(Rules, base.DocStyleTestCase):
    """TestCase checking :module:`pydocstyle`."""


class MaintainabilityIndexTestCase(Rules, base.MaintainabilityIndexTestCase):
    """TestCase checking :module:`radon` maintainability index."""


class CodeComplexityTestCase(Rules, base.CodeComplexityTestCase):
    """TestCase checking :module:`radon` code complexity."""

    max_class_complexity = 7
    max_function_complexity = 10
