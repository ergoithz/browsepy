try:
    import importlib.resources as res
except ImportError:  # pragma: no cover
    import importlib_resources as res  # to support python < 3.7


class TestFileMeta(type):
    '''
    This metaclass generates test methods for every file matching given
    rules (as class properties).

    The added test methods will call an existing meta_test method passing
    module name and filename as arguments.

    Functions from :module:`importlib.resources` (see resource_methods) are
    also injected for convenience.

    Honored class properties:
    - meta_test: called with module and filename by injected test methods.
    - meta_module: module to inspect for files
    - meta_file_extensions: filename extensions will result on test injection.
    - meta_prefix: prefix added to injected tests (defaults to `file`)
    '''

    resource_methods = (
        'contents',
        'is_resource',
        'open_binary',
        'open_text',
        'path',
        'read_binary',
        'read_text',
        )

    @classmethod
    def iter_contents(cls, module, extensions):
        for item in res.contents(module):
            if res.is_resource(module, item):
                if any(map(item.endswith, extensions)):
                    yield (module, item)
                continue
            submodule = '%s.%s' % (module, item)
            try:
                for subitem in cls.iter_contents(submodule, extensions):
                    yield subitem
            except ImportError:
                pass

    @classmethod
    def create_method(cls, module, filename, prefix, extensions):
        def test(self):
            self.meta_test(module, filename)
        strip = max(len(ext) for ext in extensions if filename.endswith(ext))
        test.__name__ = 'test_%s_%s_%s' % (
            prefix,
            module.replace('.', '_').strip('_'),
            filename[:-strip].strip('_'),
            )
        return test

    def __init__(self, name, bases, dct):
        super(TestFileMeta, self).__init__(name, bases, dct)

        # generate tests from files
        name = self.meta_module
        prefix = getattr(self, 'meta_prefix', 'file')
        extensions = self.meta_file_extensions
        for module, item in self.iter_contents(name, extensions):
            test = self.create_method(module, item, prefix, extensions)
            setattr(self, test.__name__, test)

        # add resource methods
        for method in self.resource_methods:
            if not hasattr(self, method):
                setattr(self, method, staticmethod(getattr(res, method)))
