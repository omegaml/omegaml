import json
import os
import re
import sys

from fabric.context_managers import settings, lcd, shell_env, show
from fabric.contrib.project import rsync_project
from fabric.decorators import task, roles
from fabric.operations import local, prompt, run, sudo
from fabric.state import env
from fabric.tasks import execute
from fabric.utils import fastprint
import yaml
env.use_ssh_config = True

env.shell = '/bin/bash -l -c'
env.use_ssh_config = True

env.roledefs = {
    'dokku-ssh': ['dokku-ssh'],
}


class sudosu:
    # https://github.com/fabric/fabric/issues/1013

    def __init__(self, user):
        self.user = user

    def __enter__(self):
        self.old_sudo_prefix = env.sudo_prefix
        self.old_sudo_user, env.sudo_user = env.sudo_user, self.user
        env.sudo_prefix = "sudo -S -p '%(sudo_prompt)s' su - %(sudo_user)s -c"

    def __exit__(self, a, b, c):
        env.sudo_prefix = self.old_sudo_prefix
        env.sudo_user = self.old_sudo_user


@task
@roles("dokku-ssh")
def setupdokku():
    with settings(warn_only=True):
        sudo(
            'dokku plugin:install https://github.com/dokku/dokku-mongo.git mongo')
        sudo(
            'dokku plugin:install https://github.com/dokku/dokku-mysql.git mysql')
        sudo(
            'dokku plugin:install https://github.com/dokku/dokku-rabbitmq.git rabbitmq')


@task
@roles("dokku-ssh")
def setupomega():
    with sudosu('dokku'):
        # create services
        sudo('dokku apps:create omegaml')
        sudo('dokku apps:create omjobs')
        sudo('dokku mongo:create mongodb')
        sudo('dokku mysql:create mysqldb')
        sudo('dokku rabbitmq:create rabbitmq')
        # link services
        sudo('dokku mongo:link mongodb omegaml')
        sudo('dokku mysql:link mysqldb omegaml')
        sudo('dokku rabbitmq:link rabbitmq omegaml')
        # backup stuff
        sudo('dzom mongo:backup-schedule mongodb "0 2 * * *" omegaml')


@task
def setenv(app=None):
    cmd = ('python -m stackable.encryptkeys '
           '--keysfile $HOME/.stackable/omegaml.keys '
           '--envclass EnvSettings_omegamlio')
    local(cmd)
    if app:
        print("export APP={}".format(app))
    