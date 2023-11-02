#!/usr/bin/env python3
# quick hack according to https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json

import requests
from subprocess import run


def get_chromedriver(version, platform):
    url = 'https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json'
    releases = requests.get(url).json()
    downloads = [r['downloads']['chromedriver'] for r in releases['versions'] if r['version'] == version]
    match = [d for d in downloads[-1] if d['platform'] == platform]
    if not match:
        raise ValueError('no chromedriver found for version {} and platform {}'.format(version, platform))
    cmds = [
        f"curl {match[0]['url']} -S -s -o /tmp/chromedriver.zip",
        f"unzip -o -j -d /tmp /tmp/chromedriver.zip",
        f"sudo mv /tmp/chromedriver /usr/local/bin/chromedriver",
        f"sudo chmod +x /usr/local/bin/chromedriver",
    ]
    for cmd in cmds:
        result = run(cmd.split(' '), capture_output=True)
        print(result)

def current_chrome():
    cmd = ['google-chrome', '--version']
    result = run(cmd, capture_output=True)
    # result is of the form: Google Chrome 91.0.4472.114
    version = result.stdout.decode('utf-8').split(' ')[2].strip()
    return version

if __name__ == '__main__':
    version = current_chrome()
    platform = 'linux64'
    get_chromedriver(version, platform)