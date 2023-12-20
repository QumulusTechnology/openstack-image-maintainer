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
from pathlib import Path
import math
import urllib.request
import time
import subprocess


from jsonpath_ng import jsonpath, parse
from os import environ as env
import glanceclient.v2.client as glclient

from keystoneauth1.identity import v3
from keystoneauth1 import session
from keystoneclient.v3 import client
from cinderclient import client as cinder_client

from novaclient import client as nova_client
import tempfile



from openstackclient.common import clientmanager


auth = v3.Password(auth_url=env['OS_AUTH_URL']+'/v3',
                           username=env['OS_USERNAME'],
                           password=env['OS_PASSWORD'],
                           project_name="service",
                           user_domain_id="default", project_domain_id="default")
sess = session.Session(auth=auth)
ks = client.Client(session=sess)

service_account_id = ks.projects.find(name="service").id
glance = glclient.Client(session=sess)
cinder = cinder_client.Client(3,session=sess)
nova = nova_client.Client(session=sess,
        version='2')


currentPath = os.path.dirname(os.path.realpath(__file__))

flavors = nova.flavors.list()

for flavor in flavors:
    if flavor.name == "t1.small":
        flavor_id=flavor.id

class ImageType(Enum):
    centos_stream = 1
    fedora = 2
    fedora_core = 3
    debian = 4
    ubuntu = 5
    centos = 7,
    freebsd = 8,
    rocky = 9,
    arch = 10,
    cirros = 11


class Image(object):
    def __init__(self, versionNumber, versionName, imageType: ImageType):
        self.versionNumber = versionNumber
        self.versionName = versionName
        self.imageType = imageType

class ImageMetadata(object):
    def __init__(self, username, shaSumAlgotrithm, distro, image_name):
        self.username = username
        self.shaSumAlgotrithm = shaSumAlgotrithm
        self.distro = distro
        self.image_name = image_name


ImageMetadataArray = {}

ImageMetadataArray[ImageType.centos_stream] = ImageMetadata("centos","sha256sum","centos", "CentOS-Stream")
ImageMetadataArray[ImageType.fedora] = ImageMetadata("fedora","sha256sum","fedora", "Fedora-Cloud")
ImageMetadataArray[ImageType.fedora_core] = ImageMetadata("core","sha256sum","fedora-coreos", "Fedora-Core")
ImageMetadataArray[ImageType.debian] = ImageMetadata("debian","sha512sum","debian", "Debian")
ImageMetadataArray[ImageType.ubuntu] = ImageMetadata("ubuntu","sha256sum","ubuntu", "Ubuntu")
ImageMetadataArray[ImageType.centos] = ImageMetadata("centos","sha512sum","centos", "CentOS")
ImageMetadataArray[ImageType.freebsd] = ImageMetadata("rocky","sha512sum","freebsd", "FreeBSD")
ImageMetadataArray[ImageType.rocky] = ImageMetadata("centos","sha256sum","rocky","Rocky")
ImageMetadataArray[ImageType.arch] = ImageMetadata("arch","sha256sum","arch", "Arch-Linux")
ImageMetadataArray[ImageType.cirros] = ImageMetadata("cirros","md5sum","cirros","Cirros")

ImageArray: List[Image] = []


ImageArray.append(Image("7", None, ImageType.centos))
ImageArray.append(Image("8", None, ImageType.centos_stream))
ImageArray.append(Image("9", None, ImageType.centos_stream))
ImageArray.append(Image("37", None, ImageType.fedora))
ImageArray.append(Image("38", None, ImageType.fedora))
ImageArray.append(Image("39", None, ImageType.fedora))
ImageArray.append(Image(None, "stable", ImageType.fedora_core))
ImageArray.append(Image(None, "testing", ImageType.fedora_core))
ImageArray.append(Image(None, "next", ImageType.fedora_core))
ImageArray.append(Image("10", "Buster", ImageType.debian))
ImageArray.append(Image("11", "Bullseye", ImageType.debian))
ImageArray.append(Image("12", "Bookworm", ImageType.debian))
ImageArray.append(Image("13", "Trixie", ImageType.debian))
ImageArray.append(Image("18.04", "Bionic", ImageType.ubuntu))
ImageArray.append(Image("20.04", "Focal", ImageType.ubuntu))
ImageArray.append(Image("22.04", "Jammy", ImageType.ubuntu))
ImageArray.append(Image("23.04", "Lunar",  ImageType.ubuntu))
ImageArray.append(Image("22.10", "Kinetic", ImageType.ubuntu))
ImageArray.append(Image("23.10" , "Mantic", ImageType.ubuntu))
ImageArray.append(Image("8", None, ImageType.rocky))
ImageArray.append(Image("9", None, ImageType.rocky))
ImageArray.append(Image(None, "latest", ImageType.arch))
ImageArray.append(Image("12.4", None, ImageType.freebsd))
ImageArray.append(Image("13.2", None, ImageType.freebsd))
ImageArray.append(Image("14.0", None, ImageType.freebsd))
ImageArray.append(Image("0.6.2", None, ImageType.cirros))

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

for image in ImageArray:
    imageUrl = ""
    fileName = ""
    checksum = ""
    os_version_full = ""

    if image.imageType == ImageType.arch:
        imageUrl = "https://mirrors.n-ix.net/archlinux/images/latest/Arch-Linux-x86_64-cloudimg.qcow2"
        fileName = os.path.basename(imageUrl)
        checksumUrl="https://mirrors.n-ix.net/archlinux/images/latest/Arch-Linux-x86_64-cloudimg.qcow2.SHA256"
        checksum = get_checksum(checksumUrl, fileName, image.imageType)

        response = requests.get("https://mirrors.n-ix.net/archlinux/images/latest/", params={})
        if response.ok:
            response_text = response.text
        else:
            raise Exception(response.raise_for_status())
        soup = BeautifulSoup(response_text, 'html.parser')
        imageVersionArray = soup.find_all("a")[1].next_element.split("-")[4].split(".")
        os_version_full = imageVersionArray[0] + "." + imageVersionArray[1]

    if image.imageType == ImageType.freebsd:
        imageUrl = "https://download.freebsd.org/releases/VM-IMAGES/{}-RELEASE/amd64/Latest/FreeBSD-{}-RELEASE-amd64.qcow2.xz".format(image.versionNumber, image.versionNumber)
        fileName = os.path.basename(imageUrl)
        checksumUrl="https://download.freebsd.org/releases/VM-IMAGES/{}-RELEASE/amd64/Latest/CHECKSUM.SHA512".format(image.versionNumber)
        checksum = get_checksum(checksumUrl, fileName, image.imageType)

    if image.imageType == ImageType.rocky:
        imageUrl = "https://mirror.netzwerge.de/rocky-linux/{}/images/x86_64/Rocky-{}-GenericCloud-Base.latest.x86_64.qcow2".format(image.versionNumber, image.versionNumber)
        fileName = os.path.basename(imageUrl)
        checksumUrl="https://mirror.netzwerge.de/rocky-linux/{}/images/x86_64/Rocky-{}-GenericCloud-Base.latest.x86_64.qcow2.CHECKSUM".format(image.versionNumber, image.versionNumber)
        checksum = get_checksum(checksumUrl, fileName, image.imageType)


    if image.imageType == ImageType.cirros:
        imageUrl = "https://download.cirros-cloud.net/{}/cirros-{}-x86_64-disk.img".format(image.versionNumber, image.versionNumber)
        fileName = os.path.basename(imageUrl)
        checksumUrl="https://download.cirros-cloud.net/{}/MD5SUMS".format(image.versionNumber, image.versionNumber)
        checksum = get_checksum(checksumUrl, fileName, image.imageType)

    if image.imageType == ImageType.centos_stream:
        url = "https://cloud.centos.org/centos/{}-stream/x86_64/images/".format(
            image.versionNumber)
        startsWith = "https://cloud.centos.org/centos/{}-stream/x86_64/images/CentOS-Stream-GenericCloud-{}".format(
            image.versionNumber, image.versionNumber)
        imagePath = get_image_path(url, startsWith)
        imageUrl = imagePath[0]
        fileName = os.path.basename(imageUrl)
        checksum = get_checksum(imagePath[1], fileName, image.imageType)


    if image.imageType == ImageType.centos:
        url = "https://cloud.centos.org/centos/{}/images/image-index".format(image.versionNumber)
        response = requests.get(url)
        if response.ok:
            response_text = response.text
        else:
            raise Exception(response.raise_for_status())
        text1 = "^file\=CentOS-{}-x86_64-GenericCloud-\d+.qcow2.xz".format(image.versionNumber)

        pattern1 = re.compile(text1)
        pattern2 = re.compile("^checksum\=")
        pattern3 = re.compile("^\[CentOS")

        latest=False
        fileName=""
        imageNumber=0
        checksum=""
        for line in response_text.split("\n"):
            if pattern3.match(line):
                latest = False
            if pattern1.match(line):
                fileNameLocal=line[5:]
                imageNumberLocal=int(fileNameLocal.split("-")[4].split(".")[0])
                if (imageNumberLocal >= imageNumber and imageNumberLocal < 10000):
                    latest = True
                    imageNumber = imageNumberLocal
                    fileName = fileNameLocal
                else:
                    latest = False
            if latest == True:
                if pattern2.match(line):
                    checksum=line[9:]

        imageUrl = "https://cloud.centos.org/centos/{}/images/{}".format(image.versionNumber, fileName)
        fileName = os.path.basename(imageUrl)
        os_version_full = image.versionNumber + "." + str(imageNumber)


    if image.imageType == ImageType.fedora:
        url = "https://fedora.mirrorservice.org/fedora/linux/releases/{}/Cloud/x86_64/images/".format(
            image.versionNumber)
        startsWith = "https://fedora.mirrorservice.org/fedora/linux/releases/{}/Cloud/x86_64/images/Fedora-Cloud-Base-{}".format(
            image.versionNumber,image.versionNumber)
        imagePath = get_image_path(url, startsWith)
        imageUrl = imagePath[0]
        fileName = os.path.basename(imageUrl)
        checksum = get_checksum(imagePath[1], fileName, image.imageType)

    if image.imageType == ImageType.fedora_core:
        url = "https://builds.coreos.fedoraproject.org/streams/{}.json".format(
            image.versionName)
        response = requests.get(url)
        if response.ok:
            response_text = response.text
        else:
            raise Exception(response.raise_for_status())
        json_data = json.loads(response.content)

        jsonpath_expression = parse(
            '$.architectures.x86_64.artifacts.openstack.release')
        match = jsonpath_expression.find(json_data)
        os_version_full = match[0].value

        jsonpath_expression = parse(
            '$.architectures.x86_64.artifacts.openstack.formats["qcow2.xz"].disk.location')
        match = jsonpath_expression.find(json_data)
        imageUrl = match[0].value
        fileName = os.path.basename(imageUrl)

        jsonpath_expression = parse(
            '$.architectures.x86_64.artifacts.openstack.formats["qcow2.xz"].disk["sha256"]')
        match = jsonpath_expression.find(json_data)
        checksum = match[0].value

    if image.imageType == ImageType.debian:
        imageUrl = "https://cloud.debian.org/images/cloud/{}/daily/latest/debian-{}-genericcloud-amd64-daily.qcow2".format(image.versionName.lower(), image.versionNumber)
        fileName = os.path.basename(imageUrl)
        checksum = get_checksum(
            "https://cloud.debian.org/images/cloud/{}/daily/latest/SHA512SUMS".format(image.versionName.lower()), fileName, image.imageType)

    if image.imageType == ImageType.ubuntu:
        imageUrl = "https://cloud-images.ubuntu.com/{}/current/{}-server-cloudimg-amd64.img".format(image.versionName.lower(), image.versionName.lower())
        fileName = os.path.basename(imageUrl)
        checksum = get_checksum(
            "https://cloud-images.ubuntu.com/{}/current/SHA256SUMS".format(image.versionName.lower()), fileName, image.imageType)

    image_identifier = ImageMetadataArray[image.imageType].image_name.lower()

    if image.versionNumber is not None:
        image_identifier = image_identifier + "-" + image.versionNumber
    else:
        image_identifier = image_identifier + "-" + image.versionName.lower()

    existingId = ""
    existingHash = ""
    existingName = ""
    gl_image= None
    glanceImages = glance.images.list()
    for glanceImage in glanceImages:
        if "original_identifier" in glanceImage:
            if glanceImage["original_identifier"] == image_identifier:
                gl_image = glanceImage
                existingId = glanceImage.id
                existingHash = glanceImage["original_hash"]
                existingName = glanceImage.name

    if existingId == "" or existingHash != checksum:
        tmpLocation = "/tmp/{}".format(fileName)
        if os.path.exists(tmpLocation):
            os.remove(tmpLocation)
        if fileName.endswith(".xz") and os.path.exists(tmpLocation[:-3]):
            os.remove(tmpLocation[:-3])
        urllib.request.urlretrieve(imageUrl, tmpLocation)

        shaAlgorithm=ImageMetadataArray[image.imageType].shaSumAlgotrithm
        shaSum = ""

        if (fileName.endswith(".xz")):
            shaSumOutput = subprocess.run([shaAlgorithm, tmpLocation], stdout=subprocess.PIPE)
            shaSum = shaSumOutput.stdout.decode('UTF-8').split("\n")[0].split(" ")[0]
            os.system("xz -d {}".format(tmpLocation))
            tmpLocation = tmpLocation[:-3]
        else:
            shaSumOutput = subprocess.run([shaAlgorithm, tmpLocation], stdout=subprocess.PIPE)
            shaSum = shaSumOutput.stdout.decode('UTF-8').split("\n")[0].split(" ")[0]
        if (checksum != shaSum):
            raise Exception("{} checksum is not {}".format(tmpLocation, checksum))

        if image.imageType != ImageType.fedora_core and image.imageType != ImageType.freebsd and image.imageType != ImageType.cirros:
            g = guestfs.GuestFS(python_return_dict=True)
            g.add_drive_opts(tmpLocation, readonly=0)
            g.launch()
            roots = g.inspect_os()
            if len(roots) == 0:
                print("inspect_vm: no operating systems found", file=sys.stderr)
                sys.exit(1)

            for root in roots:
                print("Root device: %s" % root)

                major_version=g.inspect_get_major_version(root)
                minor_version=g.inspect_get_minor_version(root)

                print("  Product name: %s" % (g.inspect_get_product_name(root)))
                print("  Version:      %d.%d" %
                    (major_version,
                    minor_version))
                print("  Type:         %s" % (g.inspect_get_type(root)))
                print("  Distro:       %s" % (g.inspect_get_distro(root)))

                if ImageType != ImageType.arch:
                    os_version_full="%d.%d" % (major_version,minor_version)

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
                g = None

        rawImageLocation="/tmp/" + Path(tmpLocation).stem + ".raw"
        if os.path.exists(rawImageLocation):
            os.remove(rawImageLocation)


        process = subprocess.Popen(['qemu-img', 'info', tmpLocation], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        file_format=""
        disk_size=""
        for line in process.stdout:
            lineArray=line.decode("utf-8").strip().split(":")
            if (lineArray[0]=="file format"):
                file_format=lineArray[1].strip()
            if (lineArray[0]=="virtual size"):
                disk_size=int(lineArray[1].split("(")[1].split(" ")[0])

        min_disk=math.ceil(disk_size/1073741824)
        if image.imageType != ImageType.cirros and min_disk < 5:
            min_disk=5

        if image.imageType==ImageType.fedora_core:
            image_name = ImageMetadataArray[image.imageType].image_name + "-" + image.versionName.capitalize()
            image.versionNumber =  os_version_full.split(".")[0]
        elif image.imageType==ImageType.arch:
            image_name = ImageMetadataArray[image.imageType].image_name + "-" + image.versionName.capitalize()
            image.versionNumber = image.versionName
        elif image.versionName is not None:
            image_name = ImageMetadataArray[image.imageType].image_name + "-" + image.versionNumber + "-" + image.versionName.capitalize()
        else:
            image_name = ImageMetadataArray[image.imageType].image_name + "-" + image.versionNumber

        image = glance.images.create(
            name=image_name,
            is_public='True',
            disk_format=file_format,
            container_format="bare",
            hw_qemu_guest_agent="yes",
            hw_rng_model="virtio",
            hw_architecture="x86_64",
            os_distro=ImageMetadataArray[image.imageType].distro,
            original_hash=checksum,
            os_version=image.versionNumber,
            os_version_full=os_version_full,
            os_user=ImageMetadataArray[image.imageType].username,
            os_type="linux",
            architecture="x86_64",
            os_admin_user="root",
            min_disk=min_disk,
            min_ram=512,
            original_identifier=image_identifier
        )

        glance.images.upload(image.id, open(tmpLocation, 'rb'))
        os.remove(tmpLocation)

        patchBody = [
            {
                "op": "replace",
                "path": "/visibility",
                "value": "public"
            }
        ]

        glance.images._send_image_update_request(
            image_id=image.id,
            patch_body=patchBody,
        )

        if existingId != "":

            dateString = datetime.today().strftime('%Y-%m-%d')

            newImageName = "{} {} (Archived)".format(existingName, dateString)

            patchBody = [
                {
                    "op": "replace",
                    "path": "/visibility",
                    "value": "private"
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

        print(image_name + " " + imageUrl + " " + checksum)

        server=nova.servers.create(image_name,image.id,flavor_id)
        while server.status=="BUILD":
            time.sleep(3)
            server=nova.servers.get(server.id)
        nova.servers.delete(server.id)

        volume = cinder.volumes.create(size=min_disk,imageRef=image.id,name=image_name)
        while volume.status!="available":
            time.sleep(3)
            volume=cinder.volumes.get(volume.id)
        cinder.volumes.delete(volume.id)
    else:
        print("skipping image {} as glance contains identical checksum".format(image_identifier))

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
