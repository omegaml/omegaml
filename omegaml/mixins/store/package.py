class PythonPackageMixin(object):
    """
    Install and load scripts
    """
    def install(self, specs=None, keep=False):
        """
        install and load packages

        Args:
            specs (str, list): optional, package name or list of names,
                defaults to self.list()
            keep (bool): optional, will keep any packages installed in sys.path,
                defaults to False
        """
        specs = specs or self.list()
        if isinstance(specs, str):
            specs = specs.split(' ')
        for pkgname in specs:
            self.get(pkgname, keep=keep)
