
import unittest_resources.testing as bases


class TypingTestCase(bases.TypingTestCase):
    """TestCase checking :module:`mypy`."""

    meta_module = 'browsepy'


class CodeStyleTestCase(bases.CodeStyleTestCase):
    """TestCase checking :module:`pycodestyle`."""

    meta_module = 'browsepy'


class DocStyleTestCase(bases.DocStyleTestCase):
    """TestCase checking :module:`pydocstyle`."""

    meta_module = 'browsepy'


class MaintainabilityIndexTestCase(bases.MaintainabilityIndexTestCase):
    """TestCase checking :module:`radon` maintainability index."""

    meta_module = 'browsepy'


class CodeComplexityTestCase(bases.CodeComplexityTestCase):
    """TestCase checking :module:`radon` code complexity."""

    meta_module = 'browsepy'
    max_class_complexity = 7
    max_function_complexity = 7
