"""
update cluster.yml with real exo IP addresses

This is useful if you stop/restart the nodes on which case the
IP addresses can change.

Usage:
    python update-cluster.py
    >>>
    Updated cluster.yml is in ./cluster.yml. Backup in ./cluster.yml.bak

"""
from os.path import expanduser

import toml
import yaml
from libcloud.compute.providers import get_driver
from libcloud.compute.types import Provider


def get_apikey():
    """
    from exoscale.toml config file return the api key and secret

    Returns:
        key, secret
    """
    exoconfig_fn = expanduser('~/.config/exoscale/exoscale.toml')
    with open(exoconfig_fn) as fin:
        config = toml.load(fin)
    default_account = config['defaultaccount']
    account = {}
    for cur in config['accounts']:
        if not cur['account'] == default_account:
            continue
        account = cur
    return account.get('key'), account.get('secret')


def get_nodes(driver):
    """
    get keyed list of nodes

    Args:
        driver: the driver

    Returns:
        dict of name => node
    """
    nodes = driver.list_nodes()
    keyed_nodes = {node.name: node for node in nodes}
    return keyed_nodes


def update_cluster(vm_nodes):
    """
    read the cluster.yml, update the IP address, write cluster.real.yml

    Args:
        vm_nodes: dict of name => node

    Returns:
        filename of new file
    """
    outputfn = './cluster.yml'
    backupfn = './cluster.yml.bak'
    with open('./cluster.yml') as fin:
        cluster = yaml.load(fin)
    with open(backupfn, 'w') as fout:
        yaml.dump(cluster, fout)
    for cluster_node in cluster['nodes']:
        name = cluster_node['name']
        cluster_node['address'] = vm_nodes[name].public_ips[0]
    with open(outputfn, 'w') as fout:
        yaml.dump(cluster, fout)
    print(f'Updated cluster.yml is in {outputfn}. Backup in {backupfn}')


if __name__ == '__main__':
    api_key, api_secret = get_apikey()
    cls = get_driver(Provider.EXOSCALE)
    driver = cls(api_key, api_secret)
    vm_nodes = get_nodes(driver)
    update_cluster(vm_nodes)
