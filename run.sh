docker run --rm \
  --network host \
  --name image_maintainer \
  --mount source=image-temp,target=/tmp \
  --mount type=bind,source=/root/kolla/etc/kolla,target=/var/lib/image/kolla,readonly \
  --mount type=bind,source=/etc/qcp,target=/var/lib/image/qcp,readonly \
  -it docker.io/qumulus/openstack-image-maintainer:v1.0.0
