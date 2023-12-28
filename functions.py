from classes import *
from enum import Enum
from tempfile import NamedTemporaryFile
from bs4 import BeautifulSoup
from minio import Minio
import os
import sys
from requests.adapters import HTTPAdapter, Retry
from urllib.parse import urlparse
import requests
import logging

retries = Retry(connect=10, read=10, redirect=10, backoff_factor=2)

def get_config():
    script_directory = os.path.dirname(os.path.abspath(sys.argv[0]))
    config = {}
    qcp_image_maintainer_default_config_path=os.path.join(script_directory,"image_maintainer.yml.defaults")
    if os.path.isfile(qcp_image_maintainer_default_config_path):
        with open(qcp_image_maintainer_default_config_path) as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                if ':' not in line:
                    continue
                key, value = line.split(':', 1)
                if value.strip() == "True" or value.strip() == "true":
                    config[key] = True
                elif value.strip() == "False" or value.strip() == "false":
                    config[key] = False
                else:
                    config[key] = value.strip()

    qcp_image_maintainer_config_path='/etc/qcp/image_maintainer.yml'
    if os.path.isfile(qcp_image_maintainer_config_path):
        with open(qcp_image_maintainer_config_path) as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                if ':' not in line:
                    continue
                key, value = line.split(':', 1)
                if value.strip() == "True" or value.strip() == "true":
                    config[key] = True
                elif value.strip() == "False" or value.strip() == "false":
                    config[key] = False
                else:
                    config[key] = value.strip()
    return config

config = get_config()
log_level=config['logging_level'].upper()
logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s',  level=log_level)

def get_checksum(checksum_url, fileName, imageType: ImageType, image_identifier):
    config = get_config()

    checksum = ""
    response_text = ""
    if imageType == ImageType.windows_desktop or imageType == ImageType.windows_server:
        with NamedTemporaryFile() as temp_file:
            minio_url=config['minio_url']
            minio_client = Minio(minio_url)

            remaining_download_tries = 5
            download_success=False
            while remaining_download_tries > 0 and not download_success:
                try:
                    minio_client.fget_object("qcp-images", checksum_url, temp_file.name)
                    download_success=True
                except Exception as X:
                    logging.error("{}: error downloading from {} via minio on trial no: {} - error: {}".format(image_identifier, checksum_url, str(6 - remaining_download_tries),X))
                    remaining_download_tries = remaining_download_tries - 1
            with open(temp_file.name) as f:
                checksum = f.read().strip()
    else:
        response = url_get(checksum_url)
        response_text=response.text
        if not response.ok:
            logging.info("{}: error downloading from {} via http - error: {}".format(image_identifier,checksum_url,response.reason))
            return "error"
        response.close()
        response = None

    if (imageType == ImageType.centos_stream or ImageType.fedora):
        for line in response_text.split("\n"):
            lineArray = line.split(" ")
            if (len(lineArray) > 3 and lineArray[1] == "(" + fileName + ")"):
                checksum = lineArray[3]
    if (imageType == ImageType.debian):
        for line in response_text.split("\n"):
            lineArray = line.split(" ")
            if (len(lineArray) == 3 and lineArray[2] == fileName):
                checksum = lineArray[0]
    if (imageType == ImageType.ubuntu):
        for line in response_text.split("\n"):
            lineArray = line.split(" ")
            if (len(lineArray) == 2 and lineArray[1] == "*" + fileName):
                checksum = lineArray[0]
    if (imageType == ImageType.centos):
        for line in response_text.split("\n"):
            lineArray = line.split("  ")
            if (len(lineArray) == 2 and lineArray[1] == fileName):
                checksum = lineArray[0]
    if (imageType == ImageType.rocky):
        line = response_text.split("\n")[1]
        lineArray = line.split("=")
        checksum = lineArray[1].strip()
    if (imageType == ImageType.arch):
        line = response_text.split("\n")[0]
        lineArray = line.split(" ")
        checksum = lineArray[0].strip()
    if (imageType == ImageType.freebsd):
        for line in response_text.split("\n"):
            if fileName in line:
                lineArray = line.split("=")
                checksum = lineArray[1].strip()
    if (imageType == ImageType.cirros):
        for line in response_text.split("\n"):
            if fileName in line:
                lineArray = line.split(" ")
                checksum = lineArray[0].strip()
    return checksum

def get_image_path(url, startsWith, image_identifier, ext='qcow2', checksum="CHECKSUM"):
    response = url_get(url)
    if not response.ok:
        logging.info("{}: failed to download {} - error: {}".format(image_identifier,url,response.reason))
        return "error"
    response_text=response.text
    response.close()
    response = None
    soup = BeautifulSoup(response_text, 'html.parser')
    images = [url + node.get('href') for node in soup.find_all('a')
              if node.get('href').endswith(ext)]

    checksum_url = [url + node.get('href') for node in soup.find_all('a')
                    if node.get('href').endswith(checksum)][0]
    latestImage = ""
    for image in images:
        if (image.startswith(startsWith)):
            latestImage = image
    return [latestImage, checksum_url]

def get_os_vars():
    os_vars = {}
    admin_openrc_path='/etc/kolla/admin-openrc.sh'
    if os.path.isfile(admin_openrc_path):
        with open(admin_openrc_path) as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                if 'export' not in line:
                    continue
                key, value = line.replace('export ', '', 1).strip().split('=', 1)
                os_vars[key] = value.replace("'","")
    else:
        raise Exception("missing credentials file:".format(admin_openrc_path))
    return os_vars

def url_get(url: str):
    s = requests.Session()
    url_parsed=urlparse(url)
    protocol="{}://".format(url_parsed.scheme)
    s.mount(protocol, HTTPAdapter(max_retries=retries))
    response = s.get(url)
    s.close()
    s=None
    return response
