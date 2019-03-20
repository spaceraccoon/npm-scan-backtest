import os
import shutil
import requests
import tarfile
import time
import subprocess
import argparse
import threading

parser = argparse.ArgumentParser(description='backtest npm-scan on past packages.', prog='npm-scan-backtest')
parser.add_argument('-s', '--start', help='Starting UNIX timestamp')
parser.add_argument('-e', '--end', help='Ending UNIX timestamp')
parser.add_argument('-i', '--increment', help='Batch increment size', type=int)
parser.add_argument('-l', '--log', help='Log scans', default=False, action='store_true')
args = parser.parse_args()

SKIMDB_URL = 'https://skimdb.npmjs.com/registry/_design/app/_list/index/modified'
REGISTRY_URL = 'https://registry.npmjs.org/'
INCREMENT = args.increment

def extract(current_step, package_name, package_version, file_path):
    dest = os.path.join('packages', str(current_step), '{}-{}'.format(package_name, package_version))
    tar = tarfile.open(file_path)
    tar.extractall(dest)
    tar.close()
    files_list = os.listdir(os.path.join(dest, 'package'))
    for files in files_list:
        src = os.path.join(dest, 'package', files)
        shutil.move(src, dest)
    os.rmdir(os.path.join(dest, 'package'))
    os.remove(file_path)

def download(package_name, package_version, file_path):
    r = requests.get('{}{}/-/{}-{}.tgz'.format(REGISTRY_URL, package_name, package_name, package_version))
    open(file_path, 'wb').write(r.content)

def scan_next(current_step):
    r = requests.get(SKIMDB_URL, params={'startkey': args.start, 'endkey': args.end, 'limit': INCREMENT, 'skip': current_step})
    data = r.json()

    if len(data) > 1:
        for key, value in data.items():
            if key != '_updated':
                print(key)
                if not os.path.isdir(os.path.join('packages', str(current_step))):
                    os.makedirs(os.path.join('packages', str(current_step)))
                file_path = os.path.join('packages', str(current_step), '{}-{}.tgz'.format(key, value['dist-tags']['latest']))
                download(key, value['dist-tags']['latest'], file_path)
                extract(current_step, key, value['dist-tags']['latest'], file_path)
        if not os.path.isdir('output'):
            os.mkdir('output')
        try:
            subprocess.run(['sudo', 'node', 'npm-scan/bin/scan', '-p', os.path.join('packages', str(current_step)), '-o', os.path.join('output', '{}.json'.format(current_step))], timeout=120)
        except subprocess.TimeoutExpired:
            pass
        shutil.rmtree(os.path.join('packages', str(current_step)))

        if args.log:
            open('log.txt', 'a+').write('Step {}\n'.format(current_step))
            for key, value in data.items():
                if key != '_updated':
                    open('log.txt', 'a+').write('{}@{}\n'.format(key, value['dist-tags']['latest']))

    return len(data) - 1

if __name__ == '__main__':
    current_step = 0
    package_count = 10
    while package_count > 0:
        package_count = scan_next(current_step)
        current_step += INCREMENT