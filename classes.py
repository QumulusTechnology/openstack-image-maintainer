from enum import Enum

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
    cirros = 11,
    windows_desktop = 12,
    windows_server = 13,

class DownloadProtocol(Enum):
    http = 1
    minio = 2

class CompressedFileChecksum(Enum):
    compressed_file_checksum = 1
    decompressed_file_checksum = 2

class BootMethod(Enum):
    bios = 1
    uefi = 2

class InstanceFlavor(Enum):
    t1_small = 1
    t1_medium = 2
    t1_large = 3

class Image(object):
    def __init__(self, versionNumber, versionName, imageType: ImageType):
        self.versionNumber = versionNumber
        self.versionName = versionName
        self.imageType = imageType

class ImageMetadata(object):
    def __init__(self, username, shaSumAlgotrithm, distro, image_name, min_ram, instance_flavor: InstanceFlavor):
        self.username = username
        self.shaSumAlgotrithm = shaSumAlgotrithm
        self.distro = distro
        self.image_name = image_name
        self.min_ram = min_ram
        self.instance_flavor = instance_flavor

