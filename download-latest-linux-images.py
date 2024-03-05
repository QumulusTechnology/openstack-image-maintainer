#!/usr/bin/env python3

import logging
from tabnanny import check
import requests
from bs4 import BeautifulSoup
from typing import List
from tempfile import TemporaryDirectory
import json
import subprocess
import guestfs
import sys
from datetime import datetime
import re
import math
import urllib.request
import time
import subprocess
from minio import Minio
from jsonpath_ng import parse
import glanceclient.v2.client as glclient
from keystoneauth1.identity import v3
from keystoneauth1 import session
from keystoneclient.v3 import client
from cinderclient import client as cinder_client
from novaclient import client as nova_client
from functions import *
from classes import *
import string
import os
import sys


os_vars = get_os_vars()
config = get_config()

log_level=config['logging_level'].upper()
minio_url=config['minio_url']
enable_vault_ssh = config['enable_vault_ssh']
force_upload = config['force_upload']
enable_amphora = config['enable_amphora']
enable_vyos = config['enable_vyos']
enable_centos = config['enable_centos']
enable_centos_stream = config['enable_centos_stream']
enable_fedora = config['enable_fedora']
enable_fedora_core = config['enable_fedora_core']
enable_debian = config['enable_debian']
enable_ubuntu = config['enable_ubuntu']
enable_freebsd = config['enable_freebsd']
enable_rocky = config['enable_rocky']
enable_arch = config['enable_arch']
enable_cirros = config['enable_cirros']
enable_windows = config['enable_windows']
enable_windows_pre_sysprep = config['enable_windows_pre_sysprep']
enable_windows_server = config['enable_windows_server']
enable_windows_server_pre_sysprep = config['enable_windows_server_pre_sysprep']

logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s',  level=log_level)

auth_url = os_vars['OS_AUTH_URL']+'/v3'
username = os_vars['OS_USERNAME']
password = os_vars['OS_PASSWORD']
user_domain_id = os_vars['OS_USER_DOMAIN_NAME'].lower()
project_domain_id = os_vars['OS_PROJECT_DOMAIN_NAME'].lower()

auth = v3.Password(auth_url=auth_url,
                           username=username,
                           password=password,
                           project_name="service",
                           user_domain_id=user_domain_id, project_domain_id=project_domain_id)

sess = session.Session(auth=auth)
ks = client.Client(session=sess)
glance = glclient.Client(session=sess)
cinder = cinder_client.Client(3,session=sess)
nova = nova_client.Client(session=sess,
        version='2.37')

minio_client = Minio(minio_url)
service_account_id = ks.projects.find(name="service").id
currentPath = os.path.dirname(os.path.realpath(__file__))

flavor_names = set(item.name for item in InstanceFlavor)
flavor_ids = {}

flavors = nova.flavors.list()
for flavor in flavors:
    if flavor.name.replace(".","_") in flavor_names:
        flavor_ids[InstanceFlavor[flavor.name.replace(".","_")]] = flavor.id

ImageMetadataArray = {}
ImageMetadataArray[ImageType.centos_stream] = ImageMetadata("centos","sha256sum","centos", "CentOS-Stream",512,InstanceFlavor.t1_small)
ImageMetadataArray[ImageType.fedora] = ImageMetadata("fedora","sha256sum","fedora", "Fedora-Cloud",512,InstanceFlavor.t1_small)
ImageMetadataArray[ImageType.fedora_core] = ImageMetadata("core","sha256sum","fedora-coreos", "Fedora-Core",512,InstanceFlavor.t1_small)
ImageMetadataArray[ImageType.debian] = ImageMetadata("debian","sha512sum","debian", "Debian",512,InstanceFlavor.t1_small)
ImageMetadataArray[ImageType.ubuntu] = ImageMetadata("ubuntu","sha256sum","ubuntu", "Ubuntu",512,InstanceFlavor.t1_small)
ImageMetadataArray[ImageType.centos] = ImageMetadata("centos","sha512sum","centos", "CentOS",512,InstanceFlavor.t1_small)
ImageMetadataArray[ImageType.freebsd] = ImageMetadata("rocky","sha512sum","freebsd", "FreeBSD",512,InstanceFlavor.t1_small)
ImageMetadataArray[ImageType.rocky] = ImageMetadata("centos","sha256sum","rocky","Rocky",512,InstanceFlavor.t1_small)
ImageMetadataArray[ImageType.arch] = ImageMetadata("arch","sha256sum","arch", "Arch-Linux",512,InstanceFlavor.t1_small)
ImageMetadataArray[ImageType.cirros] = ImageMetadata("cirros","md5sum",None,"Cirros",128, InstanceFlavor.t1_small)
ImageMetadataArray[ImageType.windows_desktop] = ImageMetadata("admin","sha256sum","windows","Windows",4096,InstanceFlavor.c1_xlarge)
ImageMetadataArray[ImageType.windows_server] = ImageMetadata("Administrator","sha256sum","windows","WindowsServers",2048,InstanceFlavor.t1_medium)
ImageMetadataArray[ImageType.amphora] = ImageMetadata("ubuntu","sha256sum",None,"Amphora",512,InstanceFlavor.t1_small)
ImageMetadataArray[ImageType.vyos] = ImageMetadata("vyos","sha256sum",None,"Vyos",512,InstanceFlavor.t1_small)

ImageArray: List[Image] = []

if enable_amphora:
    ImageArray.append(Image("2023.2", "latest", ImageType.amphora))
if enable_vyos:
    ImageArray.append(Image("1.3", "Equuleus", ImageType.vyos))
    ImageArray.append(Image("1.4", "Sagitta", ImageType.vyos))
if enable_centos:
    ImageArray.append(Image("7", None, ImageType.centos))
if enable_centos_stream:
    ImageArray.append(Image("8", None, ImageType.centos_stream))
    ImageArray.append(Image("9", None, ImageType.centos_stream))
if enable_fedora:
    ImageArray.append(Image("37", None, ImageType.fedora))
    ImageArray.append(Image("38", None, ImageType.fedora))
    ImageArray.append(Image("39", None, ImageType.fedora))
if enable_fedora_core:
    ImageArray.append(Image(None, "stable", ImageType.fedora_core))
    ImageArray.append(Image(None, "testing", ImageType.fedora_core))
    ImageArray.append(Image(None, "next", ImageType.fedora_core))
if enable_debian:
    ImageArray.append(Image("10", "Buster", ImageType.debian))
    ImageArray.append(Image("11", "Bullseye", ImageType.debian))
    ImageArray.append(Image("12", "Bookworm", ImageType.debian))
    ImageArray.append(Image("13", "Trixie", ImageType.debian))
if enable_ubuntu:
    ImageArray.append(Image("18.04", "Bionic", ImageType.ubuntu))
    ImageArray.append(Image("20.04", "Focal", ImageType.ubuntu))
    ImageArray.append(Image("22.04", "Jammy", ImageType.ubuntu))
    ImageArray.append(Image("23.04", "Lunar",  ImageType.ubuntu))
    ImageArray.append(Image("22.10", "Kinetic", ImageType.ubuntu))
    ImageArray.append(Image("23.10" , "Mantic", ImageType.ubuntu))
if enable_rocky:
    ImageArray.append(Image("8", None, ImageType.rocky))
    ImageArray.append(Image("9", None, ImageType.rocky))
if enable_arch:
    ImageArray.append(Image(None, "latest", ImageType.arch))
if enable_freebsd:
    ImageArray.append(Image("12.4", None, ImageType.freebsd))
    ImageArray.append(Image("13.2", None, ImageType.freebsd))
    ImageArray.append(Image("14.0", None, ImageType.freebsd))
if enable_cirros:
    ImageArray.append(Image("0.6.2", None, ImageType.cirros))
if enable_windows:
    ImageArray.append(Image("windows-11-22h2", "Windows-11-22H2", ImageType.windows_desktop))
if enable_windows_pre_sysprep:
    ImageArray.append(Image("windows-11-22h2-pre-sysprep", "Windows-11-22H2-PreSysprep", ImageType.windows_desktop))
if enable_windows_server:
    ImageArray.append(Image("windows-server-2022-datacenter-core", "Windows-Server-Datacenter-2022-Core", ImageType.windows_server))
    ImageArray.append(Image("windows-server-2022-datacenter-desktop", "Windows-Server-Datacenter-2022-Desktop", ImageType.windows_server))
    ImageArray.append(Image("windows-server-2022-standard-core", "Windows-Server-Standard-2022-Core", ImageType.windows_server))
    ImageArray.append(Image("windows-server-2022-standard-desktop", "Windows-Server-Standard-2022-Desktop", ImageType.windows_server))
if enable_windows_server_pre_sysprep:
    ImageArray.append(Image("windows-server-2022-datacenter-core-pre-sysprep", "Windows-Server-Datacenter-2022-Core-PreSysprep", ImageType.windows_server))
    ImageArray.append(Image("windows-server-2022-datacenter-desktop-pre-sysprep", "Windows-Server-Datacenter-2022-Desktop-PreSysprep", ImageType.windows_server))
    ImageArray.append(Image("windows-server-2022-standard-core-pre-sysprep", "Windows-Server-Standard-2022-Core-PreSysprep", ImageType.windows_server))
    ImageArray.append(Image("windows-server-2022-standard-desktop-pre-sysprep", "Windows-Server-Standard-2022-Desktop-PreSysprep", ImageType.windows_server))

for image in ImageArray:
    imageUrl = ""
    fileName = ""
    checksum = ""
    os_version_full = ""
    download_protocol = DownloadProtocol.http
    compressed_file_checksum = CompressedFileChecksum.compressed_file_checksum
    customise_os = True
    os_type = "linux"
    os_admin_user = "root"
    boot_method = BootMethod.bios
    tpm_enabled = False
    rng_enabled = True
    hw_machine_type = None
    flavor_id = flavor_ids[ImageMetadataArray[image.imageType].instance_flavor]
    image_identifier = ImageMetadataArray[image.imageType].image_name.lower()

    if image.imageType == ImageType.windows_desktop or image.imageType == ImageType.windows_server:
       image_identifier = image.versionNumber
    elif image.versionNumber is not None:
        image_identifier = image_identifier + "-" + image.versionNumber
    else:
        image_identifier = image_identifier + "-" + image.versionName.lower()

    logging.info("{}: processing image".format(image_identifier))

    if image.imageType == ImageType.amphora:
        imageUrl = "amphora-x64-haproxy-{}-{}.qcow2".format(image.versionNumber,image.versionName)
        fileName = imageUrl
        checksumUrl = "amphora-x64-haproxy-{}-{}.qcow2.SHA256SUM".format(image.versionNumber,image.versionName)
        checksum = get_checksum(checksumUrl,None, image.imageType,image_identifier)
        if checksum == "error":
            continue
        download_protocol = DownloadProtocol.minio
        customise_os = False

    if image.imageType == ImageType.vyos:
        imageUrl = "vyos-{}-latest.qcow2".format(image.versionNumber)
        fileName = imageUrl
        checksumUrl = "vyos-{}-latest.qcow2.SHA256SUM".format(image.versionNumber)
        checksum = get_checksum(checksumUrl,None, image.imageType,image_identifier)
        if checksum == "error":
            continue
        download_protocol = DownloadProtocol.minio
        customise_os = False

    if image.imageType == ImageType.arch:
        imageUrl = "https://mirrors.n-ix.net/archlinux/images/latest/Arch-Linux-x86_64-cloudimg.qcow2"
        fileName = os.path.basename(imageUrl)
        checksumUrl="https://mirrors.n-ix.net/archlinux/images/latest/Arch-Linux-x86_64-cloudimg.qcow2.SHA256"
        checksum = get_checksum(checksumUrl, fileName, image.imageType,image_identifier)
        if checksum == "error":
            continue

        response = url_get("https://mirrors.n-ix.net/archlinux/images/latest/")
        if not response.ok:
            logging.info("{}: failed to download {} - error: {}".format(image_identifier,url,response.reason))
            continue
        response_text=response.text
        response.close()
        response = None

        soup = BeautifulSoup(response_text, 'html.parser')
        imageVersionArray = soup.find_all("a")[1].next_element.split("-")[4].split(".")
        os_version_full = imageVersionArray[0] + "." + imageVersionArray[1]

    if image.imageType == ImageType.freebsd:
        imageUrl = "https://download.freebsd.org/releases/VM-IMAGES/{}-RELEASE/amd64/Latest/FreeBSD-{}-RELEASE-amd64.qcow2.xz".format(image.versionNumber, image.versionNumber)
        fileName = os.path.basename(imageUrl)
        checksumUrl="https://download.freebsd.org/releases/VM-IMAGES/{}-RELEASE/amd64/Latest/CHECKSUM.SHA512".format(image.versionNumber)
        checksum = get_checksum(checksumUrl, fileName, image.imageType,image_identifier)
        if checksum == "error":
            continue
        customise_os = False

    if image.imageType == ImageType.rocky:
        imageUrl = "https://mirror.netzwerge.de/rocky-linux/{}/images/x86_64/Rocky-{}-GenericCloud-Base.latest.x86_64.qcow2".format(image.versionNumber, image.versionNumber)
        fileName = os.path.basename(imageUrl)
        checksumUrl="https://mirror.netzwerge.de/rocky-linux/{}/images/x86_64/Rocky-{}-GenericCloud-Base.latest.x86_64.qcow2.CHECKSUM".format(image.versionNumber, image.versionNumber)
        checksum = get_checksum(checksumUrl, fileName, image.imageType,image_identifier)
        if checksum == "error":
            continue


    if image.imageType == ImageType.cirros:
        imageUrl = "https://download.cirros-cloud.net/{}/cirros-{}-x86_64-disk.img".format(image.versionNumber, image.versionNumber)
        fileName = os.path.basename(imageUrl)
        checksumUrl="https://download.cirros-cloud.net/{}/MD5SUMS".format(image.versionNumber, image.versionNumber)
        checksum = get_checksum(checksumUrl, fileName, image.imageType,image_identifier)
        if checksum == "error":
            continue
        customise_os = False

    if image.imageType == ImageType.centos_stream:
        url = "https://cloud.centos.org/centos/{}-stream/x86_64/images/".format(
            image.versionNumber)
        startsWith = "https://cloud.centos.org/centos/{}-stream/x86_64/images/CentOS-Stream-GenericCloud-{}".format(
            image.versionNumber, image.versionNumber)
        imagePath = get_image_path(url, startsWith,image_identifier)
        if imagePath == "error":
            continue
        imageUrl = imagePath[0]
        fileName = os.path.basename(imageUrl)
        checksum = get_checksum(imagePath[1], fileName, image.imageType,image_identifier)
        if checksum == "error":
            continue


    if image.imageType == ImageType.centos:
        url = "https://cloud.centos.org/centos/{}/images/image-index".format(image.versionNumber)
        response = url_get(url)
        if not response.ok:
            logging.info("{}: failed to download {} - error: {}".format(image_identifier,url,response.reason))
            continue
        response_text = response.text
        response.close()
        response = None

        text1 = r"^file\=CentOS-{}-x86_64-GenericCloud-\d+.qcow2.xz".format(image.versionNumber)

        pattern1 = re.compile(text1)
        pattern2 = re.compile(r"^checksum\=")
        pattern3 = re.compile(r"^\[CentOS")

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
        imagePath = get_image_path(url, startsWith, image_identifier)
        if imagePath == "error":
            continue
        imageUrl = imagePath[0]
        fileName = os.path.basename(imageUrl)
        checksum = get_checksum(imagePath[1], fileName, image.imageType,image_identifier)
        if checksum == "error":
            continue

    if image.imageType == ImageType.fedora_core:
        url = "https://builds.coreos.fedoraproject.org/streams/{}.json".format(
            image.versionName)
        response = url_get(url)
        if not response.ok:
            logging.info("{}: failed to download {} - error: {}".format(image_identifier,url,response.reason))
            continue
        response_content = response.content
        response.close()
        response = None

        json_data = json.loads(response_content)

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
        customise_os = False

    if image.imageType == ImageType.debian:
        imageUrl = "https://cloud.debian.org/images/cloud/{}/daily/latest/debian-{}-genericcloud-amd64-daily.qcow2".format(image.versionName.lower(), image.versionNumber)
        fileName = os.path.basename(imageUrl)
        checksum = get_checksum(
            "https://cloud.debian.org/images/cloud/{}/daily/latest/SHA512SUMS".format(image.versionName.lower()), fileName, image.imageType,image_identifier)
        if checksum == "error":
            continue

    if image.imageType == ImageType.ubuntu:
        imageUrl = "https://cloud-images.ubuntu.com/{}/current/{}-server-cloudimg-amd64.img".format(image.versionName.lower(), image.versionName.lower())
        fileName = os.path.basename(imageUrl)
        checksum = get_checksum(
            "https://cloud-images.ubuntu.com/{}/current/SHA256SUMS".format(image.versionName.lower()), fileName, image.imageType,image_identifier)
        if checksum == "error":
            continue

    if image.imageType == ImageType.windows_desktop or image.imageType == ImageType.windows_server:
        imageUrl = "{}.qcow2.gz".format(image.versionName)
        fileName = imageUrl
        checksumUrl = "{}.qcow2.SHA256SUM".format(image.versionName)
        checksum = get_checksum(checksumUrl,None, image.imageType,image_identifier)
        if checksum == "error1":
            continue
        download_protocol = DownloadProtocol.minio
        compressed_file_checksum = CompressedFileChecksum.decompressed_file_checksum
        customise_os = False
        os_type = "windows"
        os_admin_user = ImageMetadataArray[image.imageType].username
        boot_method = BootMethod.uefi
        tpm_enabled = True
        hw_machine_type = "q35"

    existInGlance = False
    duplicateImages=[]
    for glanceImage in glance.images.list():
        if "original_identifier" in glanceImage:
            if glanceImage["original_identifier"] == image_identifier:
                if glanceImage["original_hash"] == checksum and glanceImage["status"] == "active":
                    existInGlance = True
                elif not glanceImage.name.endswith("(Archived)"):
                    duplicateImages.append(glanceImage)

    if not existInGlance or force_upload:
        logging.info("{}: downloading from {} via method {}".format(image_identifier, imageUrl, download_protocol.name))
        temp_folder = TemporaryDirectory()
        tmpLocation = os.path.join(temp_folder.name, fileName)

        remaining_download_tries = 5
        download_success=False
        while remaining_download_tries > 0 and not download_success:
            try:
                if download_protocol == DownloadProtocol.minio:
                    minio_client.fget_object("qcp-images", imageUrl, tmpLocation)
                    download_success=True
                elif download_protocol == DownloadProtocol.http:
                    urllib.request.urlretrieve(imageUrl, tmpLocation)
                    download_success=True
            except Exception as X:
                logging.error("{}: error downloading from {} via method {} on trial no: {} - error: {}".format(image_identifier, imageUrl, download_protocol.name, str(6 - remaining_download_tries),X))
                remaining_download_tries = remaining_download_tries - 1

        if not download_success:
            continue
        shaAlgorithm=ImageMetadataArray[image.imageType].shaSumAlgotrithm
        shaSum = ""
        shaSumOutput = ""

        if (fileName.endswith(".xz")) or (fileName.endswith(".gz")):

            if compressed_file_checksum == CompressedFileChecksum.compressed_file_checksum:
                shaSumOutput = subprocess.run([shaAlgorithm, tmpLocation], stdout=subprocess.PIPE)

            if (fileName.endswith(".xz")):
                os.system("xz -d {}".format(tmpLocation))
                tmpLocation = tmpLocation[:-3]
            elif (fileName.endswith(".gz")):
                os.system("gzip -d {}".format(tmpLocation))
                tmpLocation = tmpLocation[:-3]

            if compressed_file_checksum == CompressedFileChecksum.decompressed_file_checksum:
                shaSumOutput = subprocess.run([shaAlgorithm, tmpLocation], stdout=subprocess.PIPE)
        else:
            shaSumOutput = subprocess.run([shaAlgorithm, tmpLocation], stdout=subprocess.PIPE)

        shaSum = shaSumOutput.stdout.decode('UTF-8').split("\n")[0].split(" ")[0]
        if (checksum != shaSum):
            raise Exception("{} checksum is not {}".format(tmpLocation, checksum))

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

        if enable_vault_ssh and customise_os:
            os.environ["LIBGUESTFS_BACKEND"] = "direct"
            logging.info("{}: customising OS".format(image_identifier))
            g = guestfs.GuestFS(python_return_dict=True)
            g.add_drive_opts(tmpLocation, readonly=0)
            g.launch()
            roots = g.inspect_os()
            if len(roots) == 0:
                logging.error("inspect_vm: no operating systems found")
                sys.exit(1)

            for root in roots:

                major_version=g.inspect_get_major_version(root)
                minor_version=g.inspect_get_minor_version(root)

                if ImageType != ImageType.arch:
                    os_version_full="%d.%d" % (major_version,minor_version)

                mps = g.inspect_get_mountpoints(root)
                for device, mp in sorted(mps.items(), key=lambda k: len(k[0])):
                    try:
                        g.mount(mp, device)
                    except RuntimeError as msg:
                        logging.warning("%s (ignored)" % msg)

                remoteDir = "/var/lib/cloud/scripts/per-once"
                g.mkdir_p(remoteDir)
                g.copy_in(os.path.join(
                    currentPath, "install-vault-ssh.sh"), remoteDir)

                # Unmount everything.
                g.sync()
                g.umount_all()
                g = None


        if image.imageType==ImageType.windows_desktop or image.imageType==ImageType.windows_server:
            image_name = image.versionName
            image.versionNumber = image.versionNumber
        elif image.imageType==ImageType.fedora_core:
            image_name = ImageMetadataArray[image.imageType].image_name + "-" + image.versionName.capitalize()
            image.versionNumber =  os_version_full.split(".")[0]
        elif image.imageType==ImageType.arch:
            image_name = ImageMetadataArray[image.imageType].image_name + "-" + image.versionName.capitalize()
            image.versionNumber = image.versionName
        elif image.versionName is not None:
            image_name = ImageMetadataArray[image.imageType].image_name + "-" + image.versionNumber + "-" + image.versionName.capitalize()
        else:
            image_name = ImageMetadataArray[image.imageType].image_name + "-" + image.versionNumber

        if os_version_full is None or os_version_full=="":
            if image.versionNumber is not None and image.versionNumber != "":
                os_version_full = image.versionNumber
            else:
                os_version_full = image.versionName

        mapping = {}
        mapping["name"] = image_name
        mapping["disk_format"] = file_format
        mapping["container_format"] = "bare"
        mapping["hw_qemu_guest_agent"] = "yes"
        mapping["hw_rng_model"] = "virtio"
        mapping["hw_architecture"] = "x86_64"
        mapping["original_hash"] = checksum
        mapping["os_version"] = image.versionNumber
        mapping["os_version_full"] = os_version_full
        mapping["os_user"] = ImageMetadataArray[image.imageType].username
        mapping["os_type"] = os_type
        mapping["architecture"] = "x86_64"
        mapping["os_admin_user"] = os_admin_user
        mapping["min_disk"] = min_disk
        mapping["min_ram"] = ImageMetadataArray[image.imageType].min_ram
        mapping["original_identifier"] = image_identifier
        mapping["owner"] = service_account_id
        mapping["hw_cdom_bus"] = "sata"

        if ImageMetadataArray[image.imageType].distro is not None:
            mapping["os_distro"] = ImageMetadataArray[image.imageType].distro

        if image.imageType==ImageType.amphora:
            mapping["visibility"] = "private"
            mapping["tags"] = ["amphora"]

        if image.imageType!=ImageType.amphora:
            mapping["visibility"] = "public"

        if boot_method == BootMethod.uefi:
            mapping["hw_firmware_type"] = "uefi"

        if tpm_enabled:
            mapping["hw_tpm_version"] = "2.0"

        if hw_machine_type is not None:
            mapping["hw_machine_type"] = hw_machine_type

        glance_image = glance.images.create(**mapping)

        logging.info("{}: uploading image to glance".format(image_identifier))
        glance.images.upload(glance_image.id, open(tmpLocation, 'rb'))
        temp_folder.cleanup()

        for myimage in duplicateImages:
            if image.imageType==ImageType.amphora:
                glance.images.delete(myimage.id)
            else:
                dateString = datetime.today().strftime('%Y-%m-%d')
                newImageName = "{} {} (Archived)".format(myimage.name, dateString)
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
                    image_id=myimage.id,
                    patch_body=patchBody,
                )

        logging.info("{}: booting server to warm cache".format(image_identifier))
        server=nova.servers.create(image_name,glance_image.id,flavor_id,nics="none")
        while server.status=="BUILD":
            time.sleep(3)
            server=nova.servers.get(server.id)
        nova.servers.delete(server.id)
        logging.info("{}: server created".format(image_identifier))

        logging.info("{}: creating volume to warm cache".format(image_identifier))
        volume = cinder.volumes.create(size=min_disk,imageRef=glance_image.id,name=image_name)
        while volume.status!="available":
            time.sleep(3)
            volume=cinder.volumes.get(volume.id)
        cinder.volumes.delete(volume.id)
        logging.info("{}: volume created".format(image_identifier))
    else:
        logging.info("{}: skipping image as glance contains identical checksum".format(image_identifier))

# Cleaning: Delete unused archived images
logging.info('deleting unused archive images')
glanceImages = glance.images.list()
for myimage in glanceImages:
    if "original_identifier" in myimage:
        if myimage.name.endswith("(Archived)") and myimage.owner == service_account_id:
            serverList = nova.servers.list(search_opts={'all_tenants':'True', 'image': myimage.id})
            if not serverList:
                glance.images.delete(myimage.id)
                logging.info("{}: archived image {} with ID: {} deleted".format(myimage["original_identifier"], myimage.name, myimage.id))
