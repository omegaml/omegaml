import os
import subprocess


def run(om, *args, package=None, file=None, action='install', options=None, **kwargs):
    """ install packages in user environment

    Installation:
        om scripts put envinstall envinstall

    Usage:
        # install
        om datasets put requirements.txt .system/requirements.txt
        om runtime script envinstall

        # uninstall
        om runtime script envinstall run action=uninstall
    """
    lockfile = '/app/pylib/user/envinstall.lock'
    reqfile = '.system/requirements.txt'
    try:
        with open(lockfile, 'x') as flock:
            # only run if we can get an exclusive lock
            reqfn = '/tmp/envreq.txt'
            if not package:
                with open(reqfn, 'wb') as fout:
                    reqs = om.scripts.get(reqfile).read()
                    fout.write(reqs)
                reqspec = f'-r {reqfn}'
            else:
                reqspec = package
            action_opts = {
                'install': f'-U --user {reqspec}',
                'uninstall': f'-y {reqspec}'
            }
            opts = options or action_opts.get(action) or ''
            pipcmd = f'pip {action} {opts}'
            process = subprocess.run(pipcmd.split(' '),
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT,
                                     encoding='utf-8')
    except IOError as e :
        result = f'another envinstall process is running on this node: {e}'
    else:
        result = str(process.stdout)
    finally:
        try:
            os.remove(lockfile)
        except:
            pass
    return result
