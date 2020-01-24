import os

from jupyterhub.traitlets import Command, Unicode
from kubernetes.client import V1NodeSelectorTerm, V1NodeSelectorRequirement
from kubespawner import KubeSpawner
from tornado import gen

from omegacommon.auth import OmegaRestApiAuth
from omegacommon.userconf import get_user_config_from_api

affinity_role = os.environ.get('JUPYTER_AFFINITY_ROLE', 'worker').split(',')

class OmegaKubeSpawner(KubeSpawner):
    image = Unicode(
        os.environ.get('JUPYTER_IMAGE', 'omegaml/omegaml-ee:latest'),
        config=True,
        help="""
            Docker image spec to use for spawning user's containers.
            By default uses the omegaml enterprise edition image
            """
    )
    #
    namespace = Unicode(
        os.environ.get('JUPYTER_NAMESPACE', 'omegaml-services'),
        config=True,
        help="""
            Kubernetes namespace to spawn user pods in.

            If running inside a kubernetes cluster with service accounts enabled,
            defaults to the current namespace. If not, defaults to `default`
            """
    )
    # TODO understand how we can use this instead/in combination with node selector
    #node_affinity_preferred = [
    #    # https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/V1NodeSelectorTerm.md
    ##    V1NodeSelectorTerm(
    #        match_expressions=[
    #            V1NodeSelectorRequirement(key='omegaml.io/role',
    #                                      values=affinity_role,
    #                                      operator='In')
    #        ])
    #]
    #
    image_pull_policy = Unicode(
        'Always',
        config=True,
        help="""
            The image pull policy of the docker container specified in
            `image`.

            Defaults to `IfNotPresent` which causes the Kubelet to NOT pull the image
            specified in KubeSpawner.image if it already exists, except if the tag
            is `:latest`. For more information on image pull policy,
            refer to `the Kubernetes documentation <https://kubernetes.io/docs/concepts/containers/images/>`__.


            This configuration is primarily used in development if you are
            actively changing the `image_spec` and would like to pull the image
            whenever a user container is spawned.
            """
    )

    image_pull_secrets = Unicode(
        'omegamlee-secreg',
        allow_none=True,
        config=True,
        help="""
            The kubernetes secret to use for pulling images from private repository.

            Set this to the name of a Kubernetes secret containing the docker configuration
            required to pull the image.

            See `the Kubernetes documentation <https://kubernetes.io/docs/concepts/containers/images/#specifying-imagepullsecrets-on-a-pod>`__
            for more information on when and why this might need to be set, and what
            it should be set to.
            """
    )

    home_path_template = Unicode(
        '/tmp/{username}',
        config=True,
        help='Template to expand to set the user home. {userid} and {username} are expanded'
    )

    cmd = Command(['/app/scripts/omegajobs.sh'],
                  allow_none=True,
                  help="""
            The command used for starting the single-user server.
        """
                  ).tag(config=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._omega_configs = None

    def get_args(self):
        args = super().get_args()
        args.append('--singleuser')
        return args

    def start(self):
        self.log.info("***image_spec is {} cmd is {}".format(self.image, self.cmd))
        self.log.info("starting stopped")
        return super().start()

    @property
    def home_path(self):
        return self.home_path_template.format(
            userid=self.user.id,
            username=self.user.name
        )

    def _get_omega_config(self):
        if self._omega_configs is None:
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
        return self._omega_configs

    def _clear_omega_config(self):
        self._omega_configs = None

    @gen.coroutine
    def get_pod_manifest(self):
        # update traits used in super().get_pod_manifest()
        configs = self._get_omega_config()
        if 'JUPYTER_IMAGE' in configs:
            self.image = configs['JUPYTER_IMAGE']
        if 'JUPYTER_NAMESPACE' in configs:
            self.namespace = configs['JUPYTER_NAMESPACE']
        if 'JUPYTER_NODE_SELECTOR' in configs:
            self.node_selector = dict([configs['JUPYTER_NODE_SELECTOR'].split('=')])
        result = yield from super().get_pod_manifest()
        return result

    def get_env(self):
        env = super().get_env()
        # delete all env_keeps as we want the pod to start clean
        _ = [env.pop(k, None) for k in self.env_keep] #keep as is for pyminifier
        self.log.info('OmegaKubeSpawner: user environment created')
        configs = self._get_omega_config()
        env['USER'] = self.user.name
        env['HOME'] = self.home_path
        env['SHELL'] = '/bin/bash'
        env['JY_CONTENTS_MANAGER'] = 'omegajobs.omegacontentsmgr.OmegaStoreAuthenticatedContentsManager'
        env['JY_ALLOW_ROOT'] = 'yes'
        import omegaee
        env['OMEGA_ROOT'] = os.path.join(os.path.dirname(omegaee.__file__), '..')
        env['OMEGA_USERID'] = configs['OMEGA_USERID']
        env['OMEGA_APIKEY'] = configs['OMEGA_APIKEY']
        env['OMEGA_RESTAPI_URL'] = configs['OMEGA_RESTAPI_URL']
        self.log.info("***within user_env {}".format(os.getpid()))
        self._clear_omega_config()
        return env
