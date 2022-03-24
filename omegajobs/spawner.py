import shutil

from jupyterhub.spawner import LocalProcessSpawner
from jupyterhub.traitlets import Command
from traitlets import Unicode

from omegajobs.spawnermixin import OmegaNotebookSpawnerMixin
from omegaml.client.userconf import save_userconfig_from_apikey

singleuser_starter = '/app/scripts/omegajobs.sh'


class SimpleLocalProcessSpawner(OmegaNotebookSpawnerMixin, LocalProcessSpawner):
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

    cmd = Command([singleuser_starter])

    def make_preexec_fn(self, name):
        home = self.home_path

        def preexec():
            # setup paths and get omegaml config
            self.log.info('SimpleLocalProcessSpawner: exec_fn:preexec started')
            create_path()
            get_config()

        def get_config():
            self.log.info('SimpleLocalProcessSpawner: exec_fn:get_config started')
            # get user's omegaml configuration
            try:
                from omegaml import settings
                import os
                defaults = settings()
                config_file = os.path.join(self.home_path, '.omegaml', 'config.yml')
                # must be an admin user to get back actual user's config
                self.log.info(os.environ)
                self.log.info("within get_config {}".format(os.getpid()))
                user = self._config_env.pop('OMEGA_USERID')
                apikey = self._config_env.pop('OMEGA_APIKEY')
                save_userconfig_from_apikey(config_file, user, apikey, view=True)
            except Exception as e:
                self.log.error('SimpleLocalProcessSpawner: exec_fn:get_config error {}'.format(str(e)))
                raise

        def create_path():
            self.log.info('SimpleLocalProcessSpawner: exec_fn:create_path started')
            # create local paths as required by omegaml
            try:
                import os
                if os.path.exists(home):
                    shutil.rmtree(home)
                os.makedirs(home, 0o755)
                os.makedirs(os.path.join(home, 'notebooks'))
                os.makedirs(os.path.join(home, '.omegaml'))
                os.chdir(home)
                from omegaml.notebook import jupyter
                for fn in ['ipystart.py', 'ipython_config.py',
                           'jupyter_notebook_config.py']:
                    src = os.path.join(os.path.dirname(jupyter.__file__), fn)
                    dst = os.path.join(home, fn)
                    self.log.info(('SimpleLocalProcessSpawner: exec_fn:create_path '
                                   'copying {} to {}'.format(src, dst)))
                    shutil.copy(src, dst)
            except Exception as e:
                self.log.error('SimpleLocalProcessSpawner: exec_fn:create_path error {}'.format(str(e)))
                raise

        return preexec

    def user_env(self, env):
        # we don't call super because super assumes a local OS user. we don't
        self.log.info('SimpleLocalProcessSpawner: in user_env')
        return self._omega_get_env(env)
