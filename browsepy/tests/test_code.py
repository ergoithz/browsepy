import re

import unittest_resources.testing as bases


class Rules:
    """Browsepy module mixin."""

    meta_module = 'browsepy'
    meta_module_pattern = re.compile(r'^([^t]*|t(?!ests?))+$')
    meta_resource_pattern = re.compile(r'^([^t]*|t(?!ests?))+\.py$')


# class TypingTestCase(Rules, bases.TypingTestCase):
#     """TestCase checking :module:`mypy`."""
#
#     pass


class CodeStyleTestCase(Rules, bases.CodeStyleTestCase):
    """TestCase checking :module:`pycodestyle`."""


# class DocStyleTestCase(Rules, bases.DocStyleTestCase):
#     """TestCase checking :module:`pydocstyle`."""


class MaintainabilityIndexTestCase(Rules, bases.MaintainabilityIndexTestCase):
    """TestCase checking :module:`radon` maintainability index."""


class CodeComplexityTestCase(Rules, bases.CodeComplexityTestCase):
    """TestCase checking :module:`radon` code complexity."""

    max_class_complexity = 7
    max_function_complexity = 10
