class PythonPackageMixin(object):
    def install(self):
        """
        install and load all packages
        """
        for pkgname in self.list():
            self.get(pkgname)