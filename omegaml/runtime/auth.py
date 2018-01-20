import requests

from omegacli.auth import OmegaRestApiAuth
from omegaml import defaults


class RuntimeAuthentication:

    """
    The runtime authentication
    """

    def __init__(self, user, apikey):
        self.user = user
        self.apikey = apikey


def get_omega_for_task(auth=None):
    """
    Get Omega instance configured for user in auth

    If auth is passed, a request is made to OMEGA_RESTAPI_URL to
    retrieve the configuration object for this user. 

    :param auth: the RuntimeAuthentication object
    :return: the Omega instance configured for the user
    """
    import omegaml as omdefault
    if auth is not None:
        api_auth = OmegaRestApiAuth(auth.userid,
                                    auth.apikey)
        api_url = defaults.OMEGA_RESTAPI_URL
        resp = requests.get(api_url, auth=auth)
        fail_msg = ("Not authenticated using --userid {args.userid}"
                    " --apikey {args.apikey}, error was {resp.status_code}, {resp.content}")
        assert resp.status_code == 200, fail_msg.format(**locals())
        configs = resp.json()
        config = configs['objects'][0]['data']
        mongo_url = config['OMEGA_MONGO_URL']
        backend = config['OMEGA_RESULT_BACKEND']
        om = omdefault.Omega(mongo_url, backend)
    else:
        om = omdefault
    return om
