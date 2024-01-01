#!/bin/bash

sudo mkdir -p -m 755 /etc/kolla /etc/qcp

sudo cp  --no-preserve=all /var/lib/image/qcp/image_maintainer.yml /etc/qcp 2> /dev/null

set -e

sudo cp  --no-preserve=all /var/lib/image/kolla/admin-openrc.sh /etc/kolla

$(dirname "$0")/download-latest-linux-images.py

rm -rf /tmp/*
