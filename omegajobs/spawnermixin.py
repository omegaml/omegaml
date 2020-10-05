from kubespawner.spawner import EventReflector, PodReflector

from omegaml.client.auth import OmegaRestApiAuth
from omegaml.client.userconf import get_user_config_from_api
from omegaml.util import dict_merge


class OmegaNotebookSpawnerMixin:
    def __init__(self, *args, **kwargs):
        self._omega_configs = None
        super().__init__(*args, **kwargs)

    @property
    def home_path(self):
        return self.home_path_template.format(
            userid=self.user.id,
            username=self.user.name
        )

    def get_args(self):
        args = super().get_args()
        args.append('--singleuser')
        return args

    def _get_omega_config(self, reload=False):
        self.log.info("*** loading omegaml config for user {}".format(self.user.name))
        if reload or self._omega_configs is None:
            self.log.info("*** requesting config for user {}".format(self.user.name))
            from omegaml import settings
            defaults = settings()
            admin_user = defaults.OMEGA_JYHUB_USER
            admin_apikey = defaults.OMEGA_JYHUB_APIKEY
            api_auth = OmegaRestApiAuth(admin_user, admin_apikey)
            configs = get_user_config_from_api(api_auth, api_url=None,
                                               requested_userid=self.user.name,
                                               view=True)
            configs = configs['objects'][0]['data']
            configs['OMEGA_RESTAPI_URL'] = defaults.OMEGA_RESTAPI_URL
            self._omega_configs = configs
            self._apply_omega_configs(self._omega_configs)
        return self._omega_configs

    def _load_config(self, cfg, section_names=None, traits=None):
        result = super()._load_config(cfg, section_names=section_names, traits=traits)
        try:
            self._get_omega_config()
        except Exception as e :
            self.log.error(f'Error loading user configuration {e}')
        return result

    def _apply_omega_configs(self, configs):
        if configs.get('JUPYTER_CONFIG'):
            # a catch-all configuration
            for k, v in configs['JUPYTER_CONFIG'].items():
                trait = k
                if hasattr(self, trait):
                    setattr(self, trait, v)
                else:
                    self.log.error('cannot set trait {trait} from {k}, as it does not exist'.format(**locals()))

    def _omega_get_env(self, env):
        import os
        from omegaml import settings
        import jupyterhub
        import omegaee

        def env_or_config(key, default=None):
            return configs.get(key) or os.environ.get(key) or default

        configs = self._get_omega_config()

        defaults = settings()
        admin_user = defaults.OMEGA_JYHUB_USER
        admin_apikey = defaults.OMEGA_JYHUB_APIKEY
        api_auth = OmegaRestApiAuth(admin_user, admin_apikey)
        configs = get_user_config_from_api(api_auth, api_url=None, requested_userid=self.user.name,
                                           view=True)
        configs = configs['objects'][0]['data']
        env['USER'] = self.user.name
        env['HOME'] = self.home_path
        env['SHELL'] = '/bin/bash'
        env['PYTHONPATH'] = '/app/pylib/user:/app/pylib/base'
        env['JY_CONTENTS_MANAGER'] = env_or_config('JY_CONTENTS_MANAGER',
                                                   'omegajobs.omegacontentsmgr.OmegaStoreAuthenticatedContentsManager')
        env['JY_DEFAULT_URL'] = os.environ.get('JY_DEFAULT_URL') or '/lab'
        env['JY_ALLOW_ROOT'] = 'yes'
        env['OMEGA_ROOT'] = os.path.join(os.path.dirname(omegaee.__file__), '..')
        env['OMEGA_APIKEY'] = configs['OMEGA_APIKEY']
        env['OMEGA_USERID'] = configs['OMEGA_USERID']
        env['OMEGA_RESTAPI_URL'] = defaults.OMEGA_RESTAPI_URL
        env['CA_CERTS_PATH'] = os.environ.get('CA_CERTS_PATH')
        self.log.info("***within user_env {}".format(os.getpid()))
        env['JY_HUB_VERSION'] = jupyterhub.__version__
        custom_envs = configs.get('JUPYTER_CONFIG', {}).get('ENVS', {})
        dict_merge(env, custom_envs)
        env_keep = list(self.env_keep)
        env_keep.extend(list(env.keys()))
        self.env_keep = env_keep
        # pass user configuration to preexecfn
        self._config_env = {
            'OMEGA_USERID': configs['OMEGA_USERID'],
            'OMEGA_APIKEY': configs['OMEGA_APIKEY'],
        }
        self.log.info("***get_env for user {}".format(self.user.name))
        return env


class PodWatchingMixin:
    """
    Augment pod watching to enable stable multi-user/multi-namespaces KubeSpawner

    This ensures that a KubeSpawner's pod and event reflectors are properly
    namespaced.

    Rationale:
        KubeSpawner starts one pod reflector, and if enabled, one events reflector
        for all instances it spawns. The reflectors are kept in a singleton dict,
        that is there is one dict for all spawners, for all users. This dict is
        kept in-memory at all times.

        The original KubeSpawner implementation starts reflectors with keys
        'pods' and 'events', replacing the reflectors on every server start.
        When used by multi-namespaced KubeSpawners, this results in the reflectors
        that were created for namespace1 being replaced for new reflectors
        created for namespace2. Eventually this leads to the KubeSpawner.poll()
        method to conclude that a user's server pod in namespace1 is no longer
        running (because it cannot see it in namespace2), upon which JupyterHub
        removes the route the pod, effectively making the server unreachable
        for the user, even while the pod is still running.

        This results in unexpected error messages as follows:

            JupyterHub base:962 User user09 server stopped, with exit code: 1
            JupyterHub proxy:281 Removing user user09 from proxy (/user/user09/)
            JupyterHub log:174 403 POST /hub/api/users/user09/activity (@10.42.8.191) 7.92m

        Note the sudden appearance of 403, which is a direct result of JupyterHub removing
        the server's route and authentication tokens.

        Another phenomenon from the original KubeSpawner implementation is that once
        a user has started his servers in namespace1, another user's servers in namespace2
        will fail to show up in the (already existing) reflector for namespace1. Since
        the KubeSpawner initial 'pods' reflector will have already been started for
        *some* user, in a multi-namespaced set up most users will see their first launch
        of a server to always fail. Worse, in a scenario where there are many users most
        users will never see any server launch to complete successfully, because the
        starts will interlace and thus continuously replace the existing 'pods' reflector
        to fail.

        This mixin overcomes all of this by ensuring that each namespace gets one reflector.

    See Also:
        KubeSpawner.start
        JupyterHub.user_stopped
    """

    def _start_watching_pods(self, replace=False):
        " make the pods reflector namespaced "
        return self._start_reflector(self._reflector_name_for('pods'),
                                     PodReflector,
                                     replace=replace)

    def _start_watching_events(self, replace=False):
        " make the pods reflector namespaced "
        return self._start_reflector(
            self._reflector_name_for('events'),
            EventReflector,
            fields={"involvedObject.kind": "Pod"},
            replace=replace,
        )

    def _reflector_name_for(self, kind):
        return '{}-{}'.format(kind, self.namespace)

    @property
    def pod_reflector(self):
        """alias to reflectors['pods']"""
        return self.reflectors[self._reflector_name_for('pods')]

    @property
    def event_reflector(self):
        """alias to reflectors['events']"""
        if self.events_enabled:
            return self.reflectors[self._reflector_name_for('events')]
