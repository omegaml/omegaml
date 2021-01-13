from omegaml.client.util import get_omega


class StoresCommandMixin:
    """ Common commands for OmegaStore related commands

    Usage:
        class DatasetsCommand(StoresCommandMixin, CommandBase:
            command = 'datasets'

        This will automatically provide list, drop, metadata
        commands for the store given by the command variable
    """
    command = 'unspecified'

    def put(self):
        raise NotImplementedError()

    def get(self):
        raise NotImplementedError()

    def list(self):
        om = get_omega(self.args)
        pattern = self.args.get('<pattern>')
        regexp = self.args.get('--regexp') or self.args.get('-E')
        raw = self.args.get('--raw')
        hidden = self.args.get('--hidden')
        kwargs = dict(regexp=pattern) if regexp else dict(pattern=pattern)
        store = getattr(om, self.command)
        self.logger.info(store.list(raw=raw, hidden=hidden, **kwargs))

    def drop(self):
        om = get_omega(self.args)
        name = self.args.get('<name>')
        store = getattr(om, self.command)
        self.logger.info(store.drop(name))

    def metadata(self):
        om = get_omega(self.args)
        name = self.args.get('<name>')
        store = getattr(om, self.command)
        self.logger.info(store.metadata(name).to_json())

    def plugins(self):
        om = get_omega(self.args)
        store = getattr(om, self.command)
        for kind, plugincls in store.defaults.OMEGA_STORE_BACKENDS.items():
            self.logger.info(kind, plugincls.__doc__)

    def mixins(self):
        om = get_omega(self.args)
        store = getattr(om, self.command)
        for kind, plugincls in store.defaults.OMEGA_STORE_MIXINS.items():
            self.logger.info(kind, plugincls.__doc__)
