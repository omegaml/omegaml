import requests

import requests
from omegajobs.hubauth import TokenAuthentication


class JupyterHub(object):
    """
    Client API to JupyterHub
    see http://jupyterhub.readthedocs.io/en/latest/_static/rest-api/index.html#operation--users--name--server-delete
    """

    def __init__(self, username, token, url):
        """
        :param username: the admin user. must be listed in c.JupyterHub.api_tokens and c.Authenticator.admin_users
        :param token: the token as per c.JupyterHub.api_tokens
        :param url: the hub API url, typically host:port/hub/api
        """
        self.username = username
        self.token = token
        self.url = url

    def geturl(self, path, query=None):
        apiuri = '/hub/api/'
        url = '{}{}{}'.format(self.url, apiuri, path)
        if query:
            url += '?{}'.format(query)
        return url

    def get_credentials(self, token=None):
        return TokenAuthentication(token or self.token)

    def get_usertoken(self, username, password):
        auth = {
            'username': username,
            'password': password
        }
        resp = requests.post(self.geturl('authorizations/token'), json=auth)
        return resp.json().get('token')

    def create_user(self, username):
        # http://jupyterhub.readthedocs.io/en/latest/_static/rest-api/index.html#operation--users-post
        users = {
            'usernames': [username],
            'admin': False,
        }
        resp = requests.post(self.geturl('users'), json=users, auth=self.get_credentials())
        return resp

    def start_notebook(self, username):
        auth = self.get_credentials()
        resp = requests.post(self.geturl('users/{}/server'.format(username)), auth=auth)
        return resp

    def stop_notebook(self, username):
        auth = self.get_credentials()
        resp = requests.delete(self.geturl('users/{}/server'.format(username)), auth=auth)
        return resp

    def routes(self):
        auth = self.get_credentials()
        resp = requests.get(self.geturl('proxy'), auth=auth)
        return resp.json()

    def notebook_url(self, username):
        userkey = '/user/{}/'.format(username)
        nburl = '{}{}tree'.format(self.url, userkey)
        return nburl
