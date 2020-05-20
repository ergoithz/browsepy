
import os
import unittest


class DebuggerTextTestResult(unittest._TextTestResult):  # pragma: no cover
    def __init__(self, stream, descriptions, verbosity, debugger):
        self.debugger = debugger
        self.shouldStop = True
        supa = super(DebuggerTextTestResult, self)
        supa.__init__(stream, descriptions, verbosity)

    def addError(self, test, exc_info):
        self.debugger(exc_info)
        super(DebuggerTextTestResult, self).addError(test, exc_info)

    def addFailure(self, test, exc_info):
        self.debugger(exc_info)
        super(DebuggerTextTestResult, self).addFailure(test, exc_info)


class DebuggerTextTestRunner(unittest.TextTestRunner):  # pragma: no cover
    debugger = os.environ.get('UNITTEST_DEBUG', 'none')
    test_result_class = DebuggerTextTestResult

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('verbosity', 2)
        super(DebuggerTextTestRunner, self).__init__(*args, **kwargs)

    @staticmethod
    def debug_none(exc_info):
        pass

    @staticmethod
    def debug_pdb(exc_info):
        import pdb
        pdb.post_mortem(exc_info[2])

    @staticmethod
    def debug_ipdb(exc_info):
        import ipdb
        ipdb.post_mortem(exc_info[2])

    @staticmethod
    def debug_pudb(exc_info):
        import pudb
        pudb.post_mortem(exc_info[2], exc_info[1], exc_info[0])

    def _makeResult(self):
        return self.test_result_class(
            self.stream, self.descriptions, self.verbosity,
            getattr(self, 'debug_%s' % self.debugger, self.debug_none)
            )
