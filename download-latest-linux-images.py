#!/usr/bin/env python3

from tabnanny import check
import requests
from bs4 import BeautifulSoup
from typing import List, Dict
from enum import Enum
import os
import json
import subprocess
import guestfs
import sys
from datetime import datetime
import re

from jsonpath_ng import jsonpath, parse
from os import environ as env
import glanceclient.v2.client as glclient
import keystoneclient.v3.client as ksclient
from novaclient import client as nova_client

from os_client_config import config as cloud_config

from openstackclient.common import clientmanager


keystone = ksclient.Client(auth_url=env['OS_AUTH_URL'],
                           username=env['OS_USERNAME'],
                           password=env['OS_PASSWORD'],
                           tenant_name=env['OS_TENANT_NAME'],
                           region_name=env['OS_REGION_NAME'])


glance_endpoint = keystone.service_catalog.url_for(service_type='image')
glance = glclient.Client(glance_endpoint, token=keystone.auth_token)

nova = nova_client.Client( 
        version='2',
        auth_token=keystone.auth_token,
        auth_url=env['OS_AUTH_URL'])

currentPath = os.path.dirname(os.path.realpath(__file__))


class ImageType(Enum):
    centos_stream = 1
    fedora = 2
    fedora_core = 3
    debian = 4
    ubuntu = 5
    centos = 7


class Image(object):
    def __init__(self, version, imageType: ImageType):
        self.version = version
        self.imageType = imageType


ImageArray: List[Image] = []


ImageArray.append(Image("7", ImageType.centos))
ImageArray.append(Image("8", ImageType.centos_stream))
ImageArray.append(Image("9", ImageType.centos_stream))
ImageArray.append(Image("36", ImageType.fedora))
ImageArray.append(Image("stable", ImageType.fedora_core))
ImageArray.append(Image("9", ImageType.debian))
ImageArray.append(Image("10", ImageType.debian))
ImageArray.append(Image("18.04-bionic", ImageType.ubuntu))
ImageArray.append(Image("20.04-focal", ImageType.ubuntu))
ImageArray.append(Image("22.04-jammy", ImageType.ubuntu))
ImageArray.append(Image("22.10-kinetic", ImageType.ubuntu))


def get_image_path(url, startsWith, ext='qcow2', checksum="CHECKSUM", params={}):
    response = requests.get(url, params=params)
    if response.ok:
        response_text = response.text
    else:
        raise Exception(response.raise_for_status())
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


def get_checksum(checksum_url, fileName, imageType: ImageType):
    checksum = ""
    response = requests.get(checksum_url)
    if response.ok:
        response_text = response.text
    else:
        raise Exception(response.raise_for_status())
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
    return checksum


for image in ImageArray:
    # imageName = "Fedora-Cloud-36"
    # imageUrl = "https://fedora.mirrorservice.org/fedora/linux/releases/36/Cloud/x86_64/images/Fedora-Cloud-Base-36-1.5.x86_64.qcow2"
    # fileName = "Fedora-Cloud-Base-36-1.5.x86_64.qcow2"
    # checksum = "ca9e514cc2f4a7a0188e7c68af60eb4e573d2e6850cc65b464697223f46b4605"
    os_distro = ""
    imageName = ""
    imageUrl = ""
    fileName = ""
    checksum = ""

    if image.imageType == ImageType.centos_stream:
        url = "https://cloud.centos.org/centos/{}-stream/x86_64/images/".format(
            image.version)
        startsWith = "https://cloud.centos.org/centos/{}-stream/x86_64/images/CentOS-Stream-GenericCloud-{}".format(
            image.version, image.version)
        imagePath = get_image_path(url, startsWith)
        imageUrl = imagePath[0]
        fileName = os.path.basename(imageUrl)
        checksum = get_checksum(imagePath[1], fileName, image.imageType)
        imageName = "CentOS-Stream-{}".format(image.version)
        os_distro = "centos"

    if image.imageType == ImageType.centos:
        url = "https://cloud.centos.org/centos/{}/images/image-index".format(
            image.version)

        response = requests.get(url)
        if response.ok:
            response_text = response.text
        else:
            raise Exception(response.raise_for_status())

        text1 = "^file\=CentOS-{}-x86_64-GenericCloud-".format(
             image.version)
        pattern1 = re.compile(text1)
        pattern2 = re.compile("^checksum\=")

        latest=False
        fileName=""
        imageNumber=0
        checksum=""
        for line in response_text.split("\n"):
            if pattern1.match(line):
                fileNameLocal=line[5:]
                imageNumberLocal=int(fileNameLocal.split("-")[4].split(".")[0])
                if (imageNumberLocal > imageNumber and imageNumberLocal < 10000):
                    latest = True
                    imageNumber = imageNumberLocal
                    fileName = fileNameLocal
                else:
                    latest = False
            if latest == True:
                if pattern2.match(line):
                    checksum=line[9:]

        imageUrl = "https://cloud.centos.org/centos/{}/images/{}".format(
            image.version, fileName)
        fileName = os.path.basename(imageUrl)
        os_distro = "centos"
        imageName = "CentOS-{}".format(image.version)

    if image.imageType == ImageType.fedora:
        url = "https://fedora.mirrorservice.org/fedora/linux/releases/{}/Cloud/x86_64/images/".format(
            image.version)
        startsWith = "https://fedora.mirrorservice.org/fedora/linux/releases/36/Cloud/x86_64/images/Fedora-Cloud-Base-{}".format(
            image.version)
        imagePath = get_image_path(url, startsWith)
        imageUrl = imagePath[0]
        fileName = os.path.basename(imageUrl)
        checksum = get_checksum(imagePath[1], fileName, image.imageType)
        imageName = "Fedora-Cloud-{}".format(image.version)
        os_distro = "fedora-cloud"

    if image.imageType == ImageType.fedora_core:
        url = "https://builds.coreos.fedoraproject.org/streams/{}.json".format(
            image.version)
        response = requests.get(url)
        if response.ok:
            response_text = response.text
        else:
            raise Exception(response.raise_for_status())
        json_data = json.loads(response.content)

        jsonpath_expression = parse(
            '$.architectures.x86_64.artifacts.openstack.release')
        match = jsonpath_expression.find(json_data)
        version = match[0].value
        imageName = "Fedora-Core-{}".format(version.split(".")[0])

        jsonpath_expression = parse(
            '$.architectures.x86_64.artifacts.openstack.formats["qcow2.xz"].disk.location')
        match = jsonpath_expression.find(json_data)
        imageUrl = match[0].value
        fileName = os.path.basename(imageUrl)

        jsonpath_expression = parse(
            '$.architectures.x86_64.artifacts.openstack.formats["qcow2.xz"].disk["uncompressed-sha256"]')
        match = jsonpath_expression.find(json_data)
        checksum = match[0].value
        os_distro = "fedora-coreos"

    if image.imageType == ImageType.debian:
        imageName = "Debian-{}".format(image.version)
        imageUrl = "https://cloud.debian.org/cdimage/cloud/OpenStack/current-{}/debian-{}-openstack-amd64.qcow2".format(
            image.version, image.version)
        fileName = os.path.basename(imageUrl)
        checksum = get_checksum(
            "https://cloud.debian.org/cdimage/cloud/OpenStack/current-{}/SHA256SUMS".format(image.version), fileName, image.imageType)
        os_distro = "ubuntu"

    if image.imageType == ImageType.ubuntu:
        versionNumber = image.version.split("-")[0]
        versionName = image.version.split("-")[1]
        imageName = "Ubuntu-{}-{}".format(versionNumber,
                                          versionName.capitalize())
        imageUrl = "https://cloud-images.ubuntu.com/{}/current/{}-server-cloudimg-amd64.img".format(
            versionName, versionName)
        fileName = os.path.basename(imageUrl)
        checksum = get_checksum(
            "https://cloud-images.ubuntu.com/{}/current/SHA256SUMS".format(versionName), fileName, image.imageType)
        os_distro = "ubuntu"

    tmpLocation = "/tmp/{}".format(fileName)
    if os.path.exists(tmpLocation):
        os.remove(tmpLocation)
    if fileName.endswith(".xz") and os.path.exists(tmpLocation[:-3]):
        os.remove(tmpLocation[:-3])
    os.system("curl -L -s {} --output {}".format(imageUrl, tmpLocation))

    sha256sumOutputXz = ""
    sha256sumXz = ""

    if (fileName.endswith(".xz")):
        sha256sumOutputXz = subprocess.run(['sha256sum', tmpLocation], stdout=subprocess.PIPE)
        sha256sumXz = sha256sumOutputXz.stdout.decode('UTF-8').split("\n")[0].split(" ")[0]
        os.system("xz -d {}".format(tmpLocation))
        tmpLocation = tmpLocation[:-3]
    sha256sumOutput = subprocess.run(
        ['sha256sum', tmpLocation], stdout=subprocess.PIPE)
    sha256sum = sha256sumOutput.stdout.decode(
        'UTF-8').split("\n")[0].split(" ")[0]
    if (checksum != sha256sum and sha256sumXz != "" and sha256sumXz != sha256sumXz):
        raise Exception("{} checksum is not {}".format(tmpLocation, checksum))

    if image.imageType != ImageType.fedora_core:
        g = guestfs.GuestFS(python_return_dict=True)
        g.add_drive_opts(tmpLocation, readonly=0)
        g.launch()
        roots = g.inspect_os()
        if len(roots) == 0:
            print("inspect_vm: no operating systems found", file=sys.stderr)
            sys.exit(1)

        for root in roots:
            print("Root device: %s" % root)

            # Print basic information about the operating system.
            print("  Product name: %s" % (g.inspect_get_product_name(root)))
            print("  Version:      %d.%d" %
                  (g.inspect_get_major_version(root),
                   g.inspect_get_minor_version(root)))
            print("  Type:         %s" % (g.inspect_get_type(root)))
            print("  Distro:       %s" % (g.inspect_get_distro(root)))

            # Mount up the disks, like guestfish -i.

            # Sort keys by length, shortest first, so that we end up
            # mounting the filesystems in the correct order.

            mps = g.inspect_get_mountpoints(root)
            for device, mp in sorted(mps.items(), key=lambda k: len(k[0])):
                try:
                    g.mount(mp, device)
                except RuntimeError as msg:
                    print("%s (ignored)" % msg)

            remoteDir = "/var/lib/cloud/scripts/per-once"
            g.mkdir_p(remoteDir)
            g.copy_in(os.path.join(
                currentPath, "install-vault-ssh.sh"), remoteDir)

            # Unmount everything.
            g.sync()
            g.umount_all()

    existingId = ""
    glanceImages = glance.images.list()
    for glanceImage in glanceImages:
        if glanceImage.name == imageName:
            existingId = glanceImage.id

    image = glance.images.create(
        name=imageName,
        is_public='True',
        disk_format="qcow2",
        container_format="bare",
        hw_qemu_guest_agent="yes",
        hw_rng_model="virtio",
        hw_architecture="x86_64",
        os_distro=os_distro

    )

    glance.images.upload(image.id, open(tmpLocation, 'rb'))

    patchBody = [
        {
            "op": "replace",
            "path": "/visibility",
            "value": "public"
        },
        {
            "op": "replace",
            "path": "/owner",
            "value": "f658461a492f4d68846843779506a194"
        },
    ]

    glance.images._send_image_update_request(
        image_id=image.id,
        patch_body=patchBody,
    )

    if existingId != "":

        dateString = datetime.today().strftime('%Y-%m-%d')

        newImageName = "{} {} (Archived)".format(imageName, dateString)

        patchBody = [
            {
                "op": "replace",
                "path": "/visibility",
                "value": "private"
            },
            {
                "op": "replace",
                "path": "/owner",
                "value": "7b41202e0f59454dbcb56e3c5838893f"
            },
            {
                "op": "replace",
                "path": "/name",
                "value": newImageName
            }
        ]

        glance.images._send_image_update_request(
            image_id=existingId,
            patch_body=patchBody,
        )

    os.remove(tmpLocation)

    print(imageName + " " + imageUrl + " " + checksum)


# Cleaning: Delete unused archived images
print('#############################')
print('Delete Unused Archived Images')

glanceImages = glance.images.list()

for glanceImage in glanceImages:
    if "Archived" in glanceImage.name:
        serverList = nova.servers.list(search_opts={'all_tenants':'True', 'image': glanceImage.id}) 
        if not serverList:
            glance.images.delete(glanceImage.id)
            print("  Archived Image: %s with ID: %s deleted" % (glanceImage.name, glanceImage.id))

