#!/bin/bash

docker volume inspect image-temp &> /dev/null

ret=$?
if [ $ret -ne 0 ]; then
  docker volume create image-temp 1> /dev/null
fi

docker inspect image-maintainer &> /dev/null
ret=$?
if [ $ret -eq 0 ]; then
  echo "image-maintainer is already running"
else
  docker pull repo.qumulus.io/qcp-images/openstack-image-maintainer:v1.0.0 1> /dev/null

  docker run --rm \
  --network host \
  --name image_maintainer \
  --mount source=image-temp,target=/tmp \
  --mount type=bind,source=/root/kolla/etc/kolla,target=/var/lib/image/kolla,readonly \
  --mount type=bind,source=/etc/qcp,target=/var/lib/image/qcp,readonly \
  --name image-maintainer \
  --detach \
  repo.qumulus.io/qcp-images/openstack-image-maintainer:v1.0.0 1> /dev/null
fi
