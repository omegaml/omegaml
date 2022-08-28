import os
import yaml

from omegaml.client.auth import AuthenticationEnv
from omegaml.client.userconf import ensure_api_url
from omegaml.client.util import protected
from omegaml.omega import Omega as CoreOmega
from omegaml.runtimes import OmegaRuntime


class OmegaCloud(CoreOmega):
    """
    Client API to omegaml cloud

    Provides the following APIs:

    * :code:`datasets` - access to datasets stored in the cluster
    * :code:`models` - access to models stored in the cluster
    * :code:`runtimes` - access to the cluster compute resources
    * :code:`jobs` - access to jobs stored and executed in the cluster
    * :code:`scripts` - access to lambda modules stored and executed in the cluster

    """

    def __init__(self, auth=None, **kwargs):
        """
        Initialize the client API
        """
        self.auth = auth
        super(OmegaCloud, self).__init__(**kwargs)

    def _make_runtime(self, celeryconf):
        return OmegaCloudRuntime(self, bucket=self.bucket, defaults=self.defaults, celeryconf=celeryconf)

    def _clone(self, **kwargs):
        kwargs.update(auth=self.auth)
        return super()._clone(**kwargs)

    def __repr__(self):
        return 'OmegaCloud(bucket={}, auth={})'.format(self.bucket or 'default', repr(self.auth))


class OmegaCloudRuntime(OmegaRuntime):
    """
    omegaml hosted compute cluster gateway
    """

    def __init__(self, omega, **kwargs):
        super().__init__(omega, **kwargs)
        self._auth_kwarg = protected('auth')

    def __repr__(self):
        return 'OmegaCloudRuntime(auth={})'.format(repr(self.omega.auth))

    @property
    def _common_kwargs(self):
        common = super()._common_kwargs
        common['task'].update({self._auth_kwarg: self.auth.token})
        label = common['routing'].get('label', 'default')
        if getattr(self.omega.defaults, 'OMEGA_TASK_ROUTING_ENABLED', False):
            common['routing'].update(self.build_account_routing(label))
        return common

    @property
    def auth(self):
        return self.omega.auth

    @property
    def dispatch_label(self):
        return self.omega.auth.userid

    def build_account_routing(self, label):
        # build the queue
        account_routing = {
            'label': '{self.dispatch_label}-{label}'.format(**locals())
        }
        return account_routing


def setup(userid=None, apikey=None, api_url=None, qualifier=None, bucket=None,
          view=None, make_default=True):
    import omegaml as om_mod
    api_url = ensure_api_url(api_url, om_mod._base_config)
    view = (view if view is not None
            else getattr(om_mod._base_config, 'OMEGA_SERVICES_INCLUSTER', False))
    auth_env = AuthenticationEnv.secure()
    om = auth_env.get_omega_from_apikey(userid=userid, apikey=apikey,
                                        api_url=api_url, qualifier=qualifier, view=view)
    # prepare om to be linked to default
    om.Omega = OmegaCloud
    om.setup = lambda *args, **kwargs: setup(
        **{**dict(userid=userid, apikey=apikey, qualifier=qualifier, bucket=bucket),
           **kwargs})
    om._om = om
    # ensure link to deferred instance
    om_mod.Omega = OmegaCloud
    om_mod.link(om) if make_default else None
    return om[bucket]


def setup_from_config(config_file=None, fallback=None):
    """ setup from a cloud configuration file

    If the configuration files does not contain OMEGA_USERID and OMEGA_APIKEY,
    will use given fallback.
    """
    from omegaml import _base_config
    config_file = config_file or _base_config.OMEGA_CONFIG_FILE
    if isinstance(config_file, str) and os.path.exists(config_file):
        with open(config_file, 'r') as fin:
            userconfig = yaml.safe_load(fin)
            if isinstance(userconfig, dict) and 'OMEGA_USERID' in userconfig:
                AuthenticationEnv.secure()
                try:
                    omega = setup(userid=userconfig['OMEGA_USERID'],
                                  apikey=userconfig['OMEGA_APIKEY'],
                                  qualifier=userconfig.get('OMEGA_QUALIFIER'),
                                  api_url=userconfig.get('OMEGA_RESTAPI_URL'))
                except Exception as e:
                    # TODO make this a SystemError so that OmegaDeferredIstance.setup reverts to proper defaults
                    raise SystemError(f'Could not login using config file {config_file}, error={e}')
            elif fallback:
                # if alternative loading was provided, use that
                omega = fallback()
            else:
                raise SystemError('No cloud cloud userid/apikey found in config file {}.'.format(config_file))
            return omega
    raise SystemError('Config file {} does not exist'.format(config_file))
