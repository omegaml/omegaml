#!/usr/bin/env python3
# quick hack according to https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json
import shlex

import requests
import validators
from subprocess import run


def get_chromedriver(version, platform):
    # created from information found in https://developer.chrome.com/blog/chrome-for-testing/
    download_urls = 'https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json'
    last_good_url = 'https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json'
    releases = requests.get(download_urls).json()
    downloads = [r['downloads']['chromedriver'] for r in releases['versions'] if r['version'] == version]
    if not downloads:
        releases = requests.get(last_good_url).json()
        good_version = releases['channels']['Stable']['version']
        print(f"CRITICAL chromedriver: no downloads found for Chrome {version} on {platform}")
        print(f"CRITICAL Details see https://googlechromelabs.github.io/chrome-for-testing/")
        print(f"CRITICAL The last known good version is {good_version} (channel Stable)")
        exit(1)
    # SEC: CWE-78 Command Injection
    # - status: resolved
    # - explain: url is validated and escaped in curl command to avoid injection
    match = [d for d in downloads[-1] if d['platform'] == platform]
    url = match[0]['url']
    assert validators.url(url), f"expected a valid url, got {url}"
    if not match:
        raise ValueError('no chromedriver found for version {} and platform {}'.format(version, platform))
    cmds = [
        f"curl {shlex.quote(url)} -S -s -o /tmp/chromedriver.zip",
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
