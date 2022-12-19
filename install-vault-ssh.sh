#!/usr/bin/env bash

METADATA=$(curl -s http://169.254.169.254/openstack/2018-08-27/meta_data.json)
VAULT_URL=$(echo $METADATA | awk -F'"vault_url": "' '{print $2}' | awk -F'"' '{print $1}')
VAULT_MOUNT_POINT=$(echo $METADATA | awk -F'"vault_mount_point": "' '{print $2}' | awk -F'"' '{print $1}')
VAULT_ALLOWED_ROLES=$(echo $METADATA | awk -F'"vault_allowed_roles": "' '{print $2}' | awk -F'"' '{print $1}')
PROJECT_ID=$(echo $METADATA | awk -F'"project_id": "' '{print $2}' | awk -F'"' '{print $1}')


if [ -z "$VAULT_URL" ]; then
  VAULT_URL="https://vault.qumulus.io"
fi

if [ -z "$VAULT_MOUNT_POINT" ]; then
  VAULT_MOUNT_POINT="openstack/ssh/${PROJECT_ID}"
fi

if [ -z "$VAULT_ALLOWED_ROLES" ]; then
    VAULT_ALLOWED_ROLES="*"
fi

if [ ! -f /usr/local/bin/vault-ssh-helper ]; then
    curl -s -o /usr/local/bin/vault-ssh-helper https://qumulusglobalprod.blob.core.windows.net/public-files/vault-ssh-helper
    chmod 0755 /usr/local/bin/vault-ssh-helper
    chown root:root /usr/local/bin/vault-ssh-helper
fi

mkdir -p /etc/vault-ssh-helper.d/

cat << EOF > /etc/vault-ssh-helper.d/config.hcl
vault_addr = "$VAULT_URL"
tls_skip_verify = false
ssh_mount_point = "$VAULT_MOUNT_POINT"
allowed_roles = "$VAULT_ALLOWED_ROLES"
EOF

sed -i '/^\@include common-auth$/s/^/#/' /etc/pam.d/sshd
sed -i '/^auth       substack     password-auth$/s/^/#/' /etc/pam.d/sshd
grep -qxF 'auth requisite pam_exec.so expose_authtok log=/var/log/vault_ssh.log /usr/local/bin/vault-ssh-helper -config=/etc/vault-ssh-helper.d/config.hcl' /etc/pam.d/sshd || echo 'auth requisite pam_exec.so expose_authtok log=/var/log/vault_ssh.log /usr/local/bin/vault-ssh-helper -config=/etc/vault-ssh-helper.d/config.hcl' >> /etc/pam.d/sshd

NOT_SET_PASS="not_set_pass "

grep -q "CentOS Stream release 9" /etc/redhat-release 2> /dev/null && NOT_SET_PASS=""

grep -qxF "auth optional pam_unix.so ${NOT_SET_PASS}use_first_pass nodelay" /etc/pam.d/sshd || echo "auth optional pam_unix.so ${NOT_SET_PASS}use_first_pass nodelay" >> /etc/pam.d/sshd

change_line_sshd() {
    PARAMETER=$1
    VALUE=$2
    if grep -q $PARAMETER /etc/ssh/sshd_config; then
        sed -i "/.*$PARAMETER.*/d" /etc/ssh/sshd_config
    fi
    sed -i "1s/^/$PARAMETER $VALUE\n/" /etc/ssh/sshd_config
}

change_line_sshd ChallengeResponseAuthentication yes
change_line_sshd PasswordAuthentication no
change_line_sshd UsePAM yes
change_line_sshd MaxAuthTries 15
change_line_sshd PermitRootLogin yes
change_line_sshd AcceptEnv "LANG LC_* OS_* VAULT_* ARM_* TF_*"

SELINUX_STATUS=$(getenforce 2> /dev/null)

if [ "$SELINUX_STATUS" == "Enforcing" ] ; then
#     cat << EOF > /etc/vault-ssh-helper.d/vault-otp.te
# module vault-otp 1.0;

# require {
#     type var_log_t;
#     type sshd_t;
# #    type systemd_resolved_t;
#     type http_port_t;
#     type container_file_t;
#     class file open;
#     class file create;
#     class file read;
#     class dir read;
#     class tcp_socket name_connect;
#     class lnk_file read;
#     class lnk_file getattr;

# }

# #============= sshd_t ==============
# allow sshd_t var_log_t:file open;
# allow sshd_t var_log_t:file create;
# allow sshd_t http_port_t:tcp_socket name_connect;
# allow sshd_t container_file_t:dir read;
# allow sshd_t container_file_t:file read;
# allow sshd_t container_file_t:lnk_file read;
# allow sshd_t container_file_t:file open;
# allow sshd_t container_file_t:lnk_file getattr;

# #============= systemd_resolved_t ==============
# #allow systemd_resolved_t container_file_t:file read;

# # references:
# # https://github.com/hashicorp/vault-ssh-helper/issues/31#issuecomment-335565489
# # http://www.admin-magazine.com/Articles/Credential-management-with-HashiCorp-Vault/(offset)/3
# EOF

#checkmodule -M -m -o /etc/vault-ssh-helper.d/vault-otp.mod /etc/vault-ssh-helper.d/vault-otp.te
#semodule_package -o  /etc/vault-ssh-helper.d/vault-otp.pp -m  /etc/vault-ssh-helper.d/vault-otp.mod
echo j/98+QEAAAABAAAAEAAAAI3/fPkPAAAAU0UgTGludXggTW9kdWxlAgAAABQAAAABAAAACAAAAAAAAAAJAAAAdmF1bHQtb3RwAwAAADEuMEAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAQAAAAKAAAAAAAAAAMAAAABAAAAAQAAAAAAAAB0Y3Bfc29ja2V0DAAAAAEAAABuYW1lX2Nvbm5lY3QDAAAAAAAAAAIAAAABAAAAAQAAAAAAAABkaXIEAAAAAQAAAHJlYWQIAAAAAAAAAAQAAAACAAAAAgAAAAAAAABsbmtfZmlsZQcAAAACAAAAZ2V0YXR0cgQAAAABAAAAcmVhZAQAAAAAAAAAAQAAAAMAAAADAAAAAAAAAGZpbGUGAAAAAgAAAGNyZWF0ZQQAAAADAAAAcmVhZAQAAAABAAAAb3BlbgEAAAABAAAACAAAAAEAAAAAAAAAb2JqZWN0X3JAAAAAAAAAAAAAAABAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAQAAAAEAAAACwAAAAMAAAABAAAAAQAAAAAAAABAAAAAAAAAAAAAAABodHRwX3BvcnRfdAkAAAABAAAAAQAAAAEAAAAAAAAAQAAAAAAAAAAAAAAAdmFyX2xvZ190EAAAAAQAAAABAAAAAQAAAAAAAABAAAAAAAAAAAAAAABjb250YWluZXJfZmlsZV90BgAAAAIAAAABAAAAAQAAAAAAAABAAAAAAAAAAAAAAABzc2hkX3QAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAABAAAAAQAAAAAAAAAAAAAACAAAAAEAAAAAAAAAQAAAAEAAAAABAAAAAAAAAAIAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAEAAAABAAAAAAQAAAAAAAAABAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAABAAAAAQAAAAEAAAABAAAAAAAAAEAAAABAAAAAAQAAAAAAAAACAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAQAAAAAEAAAAAAAAAAQAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAQAAAAEAAAACAAAAAQAAAAAAAABAAAAAQAAAAAEAAAAAAAAAAgAAAAAAAABAAAAAAAAAAAAAAAAAAAAAQAAAAEAAAAABAAAAAAAAAAQAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAEAAAADAAAAAQAAAAEAAAAAAAAAQAAAAEAAAAABAAAAAAAAAAIAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAEAAAABAAAAAAQAAAAAAAAAIAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAABAAAAAgAAAAEAAAABAAAAAAAAAEAAAABAAAAAAQAAAAAAAAACAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAQAAAAAEAAAAAAAAACAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAQAAAAEAAAAEAAAAAQAAAAAAAABAAAAAQAAAAAEAAAAAAAAAAgAAAAAAAABAAAAAAAAAAAAAAAAAAAAAQAAAAEAAAAABAAAAAAAAAAgAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAEAAAAEAAAAAQAAAAEAAAAAAAAAQAAAAEAAAAABAAAAAAAAAAIAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAEAAAABAAAAAAQAAAAAAAAAIAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAABAAAAAQAAAAEAAAABAAAAAAAAAEAAAABAAAAAAQAAAAAAAAACAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAQAAAAAEAAAAAAAAACAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAQAAAAQAAAACAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAEAAAABAAAAAAQAAAAAAAAAPAAAAAAAAAEAAAAAAAAAAAAAAAEAAAABAAAAAAQAAAAAAAAAPAAAAAAAAAEAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAQAAABAAAAAQAAAAAEAAAAAAAAABwAAAAAAAABAAAAAQAAAAAEAAAAAAAAAAQAAAAAAAABAAAAAQAAAAAEAAAAAAAAAAQAAAAAAAABAAAAAQAAAAAEAAAAAAAAAAwAAAAAAAABAAAAAAAAAAAAAAABAAAAAAAAAAAAAAABAAAAAAAAAAAAAAABAAAAAAAAAAAAAAABAAAAAAAAAAAAAAABAAAAAAAAAAAAAAABAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAACgAAAHRjcF9zb2NrZXQBAAAAAQAAAAEAAAADAAAAZGlyAQAAAAEAAAABAAAACAAAAGxua19maWxlAQAAAAEAAAABAAAABAAAAGZpbGUBAAAAAQAAAAEAAAABAAAACAAAAG9iamVjdF9yAgAAAAEAAAABAAAABAAAAAsAAABodHRwX3BvcnRfdAEAAAABAAAAAQAAAAkAAAB2YXJfbG9nX3QBAAAAAQAAAAEAAAAQAAAAY29udGFpbmVyX2ZpbGVfdAEAAAABAAAAAQAAAAYAAABzc2hkX3QBAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA== | base64 -d > /etc/vault-ssh-helper.d/vault-otp.pp
semodule -i /etc/vault-ssh-helper.d/vault-otp.pp
fi

systemctl reload sshd
