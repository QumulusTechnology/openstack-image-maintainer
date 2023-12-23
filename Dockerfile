FROM ubuntu:22.04

ENV IMAGE_VERSION 1.0.0
ENV IMAGE_NAME openstack-image-uploader


COPY requirements.txt requirements.txt

RUN apt update && apt upgrade -y && apt install -y python3-guestfs linux-image-kvm python3-pip-whl qemu-utils --no-install-recommends
