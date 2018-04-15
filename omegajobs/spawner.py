import os
import shutil

from traitlets import Unicode

from jupyterhub.spawner import LocalProcessSpawner

from omegacommon.userconf import save_userconfig_from_apikey


class SimpleLocalProcessSpawner(LocalProcessSpawner):
    """
    Adopted from jupyterhub-simplespawner

    A version of LocalProcessSpawner that doesn't require users to exist on
    the system beforehand.

    Note: DO NOT USE THIS FOR PRODUCTION USE CASES! It is very insecure, and
    provides absolutely no isolation between different users!
    """

    home_path_template = Unicode(
        '/tmp/{userid}',
        config=True,
        help='Template to expand to set the user home. {userid} and {username} are expanded'
    )

    @property
    def home_path(self):
        return self.home_path_template.format(
            userid=self.user.id,
            username=self.user.name
        )

    def make_preexec_fn(self, name):
        home = self.home_path
        def preexec():
            # setup paths and get omegaml config
            create_path()
            get_config()

        def get_config():
            # get user's omegaml configuration from remote
            try:
                from omegaml import defaults
                config_file = os.path.join(self.home_path, '.omegaml', 'config.yml')
                # must be an admin user to get back actual user's config
                admin_user = defaults.OMEGA_JYHUB_USER
                admin_apikey = defaults.OMEGA_JYHUB_APIKEY
                save_userconfig_from_apikey(config_file, admin_user, admin_apikey,
                                            requested_userid=self.user.name)
            except Exception as e:
                print(e)
                raise

        def create_path():
            # create local paths as required by omegaml
            try:
                if os.path.exists(home):
                    shutil.rmtree(home)
                os.makedirs(home, 0o755)
                os.makedirs(os.path.join(home, 'notebooks'))
                os.makedirs(os.path.join(home, '.omegaml'))
                os.chdir(home)
                import omegajobs
                for fn in ['ipystart.py', 'ipython_config.py',
                           'jupyter_notebook_config.py']:
                    src = os.path.join(os.path.dirname(omegajobs.__file__), fn)
                    dst = os.path.join(home, fn)
                    shutil.copy(src, dst)
            except Exception as e:
                print(e)
                raise

        return preexec

    def user_env(self, env):
        env['USER'] = self.user.name
        env['HOME'] = self.home_path
        env['SHELL'] = '/bin/bash'
        import omegaml
        env['OMEGA_ROOT'] = os.path.join(os.path.dirname(omegaml.__file__), '..')
        return env
