import os
import shlex
import subprocess
from pathlib import Path


def run(om, *args, package=None, requirements=None, action='install', options=None, **kwargs):
    """ install packages in user environment

    Installation:
        # from the command line
        om runtime env install
        # from the omegaml/runtimes/envinstall directory
        om scripts put envinstall envinstall

    Usage:
        # install
        om datasets put requirements.txt .system/requirements.txt
        om runtime script envinstall

        # uninstall
        om runtime script envinstall run action=uninstall
    """
    lockfile = '/tmp/envinstall.lock'
    reqfile_dataset = requirements or '.system/requirements.txt'  # from om.datasets
    reqfile_local = Path(om.scripts.tmppath) / 'requirements.txt'  # for pip
    package = package or ''
    package = ' '.join(package) if isinstance(package, (list, tuple)) else package
    result = 'envinstall has not been executed'
    try:
        # only run if we can get an exclusive lock to avoid parallel pip installs
        with open(lockfile, 'x') as flock:
            # -- determine requirements
            reqspec = f'{package}'
            if om.scripts.exists(reqfile_dataset):
                with open(reqfile_local, 'wb') as fout:
                    reqs = om.scripts.get(reqfile_dataset).read()
                    fout.write(reqs)
                reqspec = f'-r {reqfile_local} {reqspec}'
            assert reqspec, "specify either package= or requirements= (no default .system/requirements.txt exists)"
            # -- determine action
            action_opts = {
                'install': f'-U --user {reqspec}',
                'uninstall': f'-y {reqspec}'
            }
            opts = options or action_opts.get(action) or ''
            # run pip install
            pipcmd = f'pip {action} {opts}'
            om.logger.info(f'running {pipcmd}')
            process = subprocess.run(shlex.split(pipcmd),
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT,
                                     encoding='utf-8')
            om.logger.info(f'** finished running {pipcmd} {process}')
    except IOError as e:
        result = f'envinstall cannot run due to another pip install is running on this node: {e}'
        om.logger.error(result)
        raise ValueError(result)
    except Exception as e:
        result = f'envinstall failed due to {e}'
        om.logger.error(result)
        raise ValueError(result)
    else:
        result = str(process.stdout)
    finally:
        for fn in (lockfile, reqfile_local):
            try:
                os.remove(fn)
            except:
                pass
    return result
