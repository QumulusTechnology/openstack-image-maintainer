FROM ubuntu:22.04

ENV IMAGE_VERSION 1.0.0
ENV IMAGE_NAME openstack-image-maintainer

ARG USERNAME=image
ARG USER_UID=1000
ARG USER_GID=$USER_UID


RUN apt update && \
  apt upgrade -y && \
  apt install -y \
  python3-guestfs \
  linux-image-kvm \
  python3-pip-whl \
  qemu-utils \
  python3-pip \
  python3-dev \
  sudo \
  nano && \
  chmod +r /boot/vmlinu* && \
  groupadd --gid $USER_GID $USERNAME && \
  useradd -d /home/$USERNAME --uid $USER_UID --gid $USER_GID -m $USERNAME && \
  mkdir -p /home/$USERNAME/openstack-image-maintainer && \
  chown -R $USERNAME:$USERNAME /home/$USERNAME && \
  echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME && \
  chmod 0440 /etc/sudoers.d/$USERNAME

COPY * /home/$USERNAME/openstack-image-maintainer/
RUN pip install -r /home/$USERNAME/openstack-image-maintainer/requirements.txt

USER $USERNAME
ENTRYPOINT ["/home/image/openstack-image-maintainer/entry.sh"]
