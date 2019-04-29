import os
from typing import List

from kubespawner import KubeSpawner
from jupyterhub.traitlets import Command, Unicode

import omegaml
from omegacommon.auth import OmegaRestApiAuth
from omegacommon.userconf import get_user_config_from_api
from omegaml import defaults


class OmegaKubeSpawner(KubeSpawner):
    image_spec = Unicode(
        'omegaml/omegaml-ee:latest',
        config=True,
        help="""
            Docker image spec to use for spawning user's containers.
            By default uses the omegaml enterprise edition image
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

    def get_args(self):
        args = super().get_args()
        args.append('--singleuser')
        return args

    def start(self):
        self.log.info("***image_spec is {} cmd is {}".format(self.image_spec, self.cmd))
        self.log.info("starting stopped")
        return super().start()

    @property
    def home_path(self):
        return self.home_path_template.format(
            userid=self.user.id,
            username=self.user.name
        )

    def get_env(self):
        env = super().get_env()
        # delete all env_keeps as we want the pod to start clean
        [env.pop(k, None) for k in self.env_keep]
        self.log.info('OmegaKubeSpawner: user environment created')
        admin_user = defaults.OMEGA_JYHUB_USER
        admin_apikey = defaults.OMEGA_JYHUB_APIKEY
        api_auth = OmegaRestApiAuth(admin_user, admin_apikey)
        configs = get_user_config_from_api(api_auth, api_url=None, requested_userid=self.user.name)
        configs = configs['objects'][0]['data']
        env['USER'] = self.user.name
        env['HOME'] = self.home_path
        env['SHELL'] = '/bin/bash'
        env['JY_CONTENTS_MANAGER'] = 'omegajobs.omegacontentsmgr.OmegaStoreAuthenticatedContentsManager'
        env['JY_ALLOW_ROOT'] = 'yes'
        env['OMEGA_ROOT'] = os.path.join(os.path.dirname(omegaml.__file__), '..')
        env['OMEGA_USERID'] = configs['OMEGA_USERID']
        env['OMEGA_APIKEY'] = configs['OMEGA_APIKEY']
        env['OMEGA_RESTAPI_URL'] = defaults.OMEGA_RESTAPI_URL
        self.log.info("***within user_env {}".format(os.getpid()))
        return env
