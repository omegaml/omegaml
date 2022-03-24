import os
from jupyterhub.traitlets import Command, Unicode
from kubespawner import KubeSpawner

from omegajobs.spawnermixin import OmegaNotebookSpawnerMixin, PodWatchingMixin

affinity_role = os.environ.get('JUPYTER_AFFINITY_ROLE', 'worker').split(',')

# adopted from https://github.com/jupyterhub/zero-to-jupyterhub-k8s/blob/master/jupyterhub/files/hub/jupyterhub_config.py
TRAIT_MAP = dict((k, v) for v, k in dict([
    ('start_timeout', None),
    ('image_pull_policy', 'image.pullPolicy'),
    ('events_enabled', 'events'),
    ('extra_labels', None),
    ('extra_annotations', None),
    ('uid', None),
    ('fs_gid', None),
    ('service_account', 'serviceAccountName'),
    ('storage_extra_labels', 'storage.extraLabels'),
    ('tolerations', 'extraTolerations'),
    ('node_selector', None),
    ('node_affinity_required', 'extraNodeAffinity.required'),
    ('node_affinity_preferred', 'extraNodeAffinity.preferred'),
    ('pod_affinity_required', 'extraPodAffinity.required'),
    ('pod_affinity_preferred', 'extraPodAffinity.preferred'),
    ('pod_anti_affinity_required', 'extraPodAntiAffinity.required'),
    ('pod_anti_affinity_preferred', 'extraPodAntiAffinity.preferred'),
    ('lifecycle_hooks', None),
    ('init_containers', None),
    ('extra_containers', None),
    ('mem_limit', 'memory.limit'),
    ('mem_guarantee', 'memory.guarantee'),
    ('cpu_limit', 'cpu.limit'),
    ('cpu_guarantee', 'cpu.guarantee'),
    ('extra_resource_limits', 'extraResource.limits'),
    ('extra_resource_guarantees', 'extraResource.guarantees'),
    ('environment', 'extraEnv'),
    ('profile_list', None),
    ('extra_pod_config', None),
]).items())



class OmegaKubeSpawner(OmegaNotebookSpawnerMixin, PodWatchingMixin, KubeSpawner):
    # specifics of k8s create pod API see https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/V1PodSpec.md
    image = Unicode(
        os.environ.get('JUPYTER_IMAGE', 'omegaml/omegaml-ee:latest'),
        config=True,
        help="""
            Docker image spec to use for spawning user's containers.
            By default uses the omegaml enterprise edition image
            """
    )

    namespace = Unicode(
        os.environ.get('JUPYTER_NAMESPACE', 'omegaml-services'),
        config=True,
        help="""
            Kubernetes namespace to spawn user pods in.

            If running inside a kubernetes cluster with service accounts enabled,
            defaults to the current namespace. If not, defaults to `default`
            """
    )

    # set in omegaml configs ['CLUSTER_VOLUMES]['volumes']
    # volumes = [
    #    {
    #        'name': 'pylib',
    #        'persistent_volume_claim': {
    #              'claimName': 'worker-{username}',
    #              'readOnly': False,
    #        }
    #    }
    # ]

    # set in omegaml configs ['CLUSTER_VOLUMES]['volumeMounts']
    # volume_mounts = [
    #    {
    #        'name': 'pylib',
    #        'mountPath': '/app/pylib',
    #    }
    # ]

    # TODO understand how we can use this instead/in combination with node selector
    # node_affinity_preferred = [
    #    # https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/V1NodeSelectorTerm.md
    ##    V1NodeSelectorTerm(
    #        match_expressions=[
    #            V1NodeSelectorRequirement(key='omegaml.io/role',
    #                                      values=affinity_role,
    #                                      operator='In')
    #        ])
    # ]
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
    #
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

    def start(self):
        self.log.info("***image_spec is {} cmd is {}".format(self.image, self.cmd))
        self._get_omega_config()
        self.add_poll_callback(self._cleanup_on_stop)
        return super().start()

    async def stop(self, *args, **kwargs):
        self._cleanup_on_stop()
        result = await super().stop(*args, **kwargs)
        return result

    def get_options_form(self):
        self._get_omega_config(reload=True)
        options_form = super().get_options_form()
        return options_form

    def _cleanup_on_stop(self, *args, **kwargs):
        # polling callback
        # - Service.start => spawner.start => spawner.start_polling
        # - spawner.poll() is called polling_interval often
        # - when pod has stopped, callbacks are called
        # - we reload omega config to make sure we start afresh
        self.log.info('*** cleaning up for user {}'.format(self.user.name))
        self._get_omega_config(reload=True)

    def _apply_omega_configs(self, configs):
        self.log.info('*** resetting configs for user {}'.format(self.user.name))
        if 'JUPYTER_IMAGE' in configs:
            self.image = configs['JUPYTER_IMAGE']
        if 'JUPYTER_NAMESPACE' in configs:
            self.namespace = configs['JUPYTER_NAMESPACE']
        if 'JUPYTER_NODE_SELECTOR' in configs:
            self.node_selector = dict([configs['JUPYTER_NODE_SELECTOR'].split('=')])
        if configs.get('CLUSTER_STORAGE'):
            self.volumes = configs['CLUSTER_STORAGE']['volumes']
            self.volume_mounts = configs['CLUSTER_STORAGE']['volumeMounts']
        if configs.get('JUPYTER_CONFIG'):
            # a catch-all configuration
            for k, v in configs['JUPYTER_CONFIG'].items():
                trait = TRAIT_MAP.get(k) or k
                if hasattr(self, trait):
                    setattr(self, trait, v)
                else:
                    self.log.error('cannot set trait {trait} from {k}, as it does not exist'.format(**locals()))
        # DO NOT TOUCH UNLESS YOU KNOW WHAT YOU ARE DOING - IT TOOK MANY HOURS TO GET THIS RIGHT
        # corresponding test is in test_kubespawner.test_makepod_userspecified_jupyter_config
        # always reset the options form, otherwise it is done only once,
        # if we don't do this the options form is never updated unless the spawner and it state db is recycled
        # and any profile_list will stay the same forever
        if self.profile_list:
            self.options_form = self._render_options_form(self.profile_list)

    async def get_pod_manifest(self):
        # hook for custom manifest processing. still needed?
        self.log.info('generating pod manifest for {}'.format(self.user.name))
        result = await super().get_pod_manifest()
        return result

    def get_env(self):
        # called before make_pod
        self.log.info('OmegaKubeSpawner: get_env')
        env = super().get_env()
        return self._omega_get_env(env)
