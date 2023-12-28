#!/bin/bash

docker build . -t image:latest --network host

docker volume create image-temp 1> /dev/null
docker run --rm \
  --network host \
  --name image_maintainer \
  --mount source=image-temp,target=/tmp \
  --mount type=bind,source=/root/kolla/etc/kolla,target=/var/lib/image/kolla,readonly \
  --mount type=bind,source=/etc/qcp,target=/var/lib/image/qcp,readonly \
  -it image:latest 
docker volume rm image-temp 1> /dev/null
