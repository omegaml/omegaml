#!/usr/bin/env python

"""
consolidate pip and conda requirements

Reads pip-requirements.txt and conda-requirements.txt,
reduces pip-requirements.txt to the packages not alredy
included in conda and prints the remaining packages in
pip requirements.txt format.
"""
import sys

import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-w', help='write to output file')
args = parser.parse_args()

def read_requirements(reqfn, delim):
    with open(reqfn) as fin:
        lines = fin.readlines()
        packages = {}
        for ln in lines:
            if ln.startswith('#'):
                continue
            pkg, version = ln.split(delim, 1)
            canonical = pkg.lower().replace('-', '_')
            packages[canonical] = (pkg, version)
    return packages

def read_consolidate():
    # read and consolidate
    pip_packages = read_requirements('pip-requirements.txt', '==')
    conda_packages = read_requirements('conda-requirements.txt', '=')
    pip_only = set(pip_packages.keys()) - set(conda_packages.keys())
    return pip_only, pip_packages

def write_requirements(outf, pip_only, pip_packages):
    for pkg in sorted(pip_only):
        pkgname, version = pip_packages[pkg]
        reqline = '{pkgname}=={version}'.format(**locals())
        reqline = reqline.replace('\n', '')
        outf.write(reqline + '\n')

pip_only, pip_packages = read_consolidate()
# output remaining packages in pip requirements format
if args.w:
    count = len(pip_packages) - len(pip_only)
    print("Writing to {args.w}, de-duplicated {count} packages".format(**locals()))
    with open(args.w, 'w') as fout:
        write_requirements(fout, pip_only, pip_packages)
else:
    write_requirements(sys.stdout, pip_only, pip_packages)
