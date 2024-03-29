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
    curl -s -o /usr/local/bin/vault-ssh-helper https://qumuluspublic.blob.core.windows.net/qpc/vault-ssh-helper
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
change_line_sshd KbdInteractiveAuthentication yes
change_line_sshd UsePAM yes
change_line_sshd MaxAuthTries 15
change_line_sshd PermitRootLogin yes
change_line_sshd AcceptEnv "LANG LC_* OS_* VAULT_* ARM_* TF_*"

SELINUX_STATUS=$(getenforce 2> /dev/null)

if [ "$SELINUX_STATUS" == "Enforcing" ] ; then

    if hash checkmodule &> /dev/null && hash semodule_package &> /dev/null ; then

        cat << EOF > /etc/vault-ssh-helper.d/vault-otp.te
module vault-otp 1.0;

require {
    type var_log_t;
    type sshd_t;
    type systemd_resolved_t;
    type http_port_t;
    type container_file_t;
    class file open;
    class file create;
    class file read;
    class dir read;
    class tcp_socket name_connect;
    class lnk_file read;
    class lnk_file getattr;
    type cloud_log_t;
    type sshd_t;
    class file open;

}

#============= sshd_t ==============
allow sshd_t cloud_log_t:file open;
allow sshd_t var_log_t:file open;
allow sshd_t var_log_t:file create;
allow sshd_t http_port_t:tcp_socket name_connect;
allow sshd_t container_file_t:dir read;
allow sshd_t container_file_t:file read;
allow sshd_t container_file_t:lnk_file read;
allow sshd_t container_file_t:file open;
allow sshd_t container_file_t:lnk_file getattr;

#============= systemd_resolved_t ==============
#allow systemd_resolved_t container_file_t:file read;

# references:
# https://github.com/hashicorp/vault-ssh-helper/issues/31#issuecomment-335565489
# http://www.admin-magazine.com/Articles/Credential-management-with-HashiCorp-Vault/(offset)/3
EOF

        checkmodule -M -m -o /etc/vault-ssh-helper.d/vault-otp.mod /etc/vault-ssh-helper.d/vault-otp.te
        semodule_package -o  /etc/vault-ssh-helper.d/vault-otp.pp -m  /etc/vault-ssh-helper.d/vault-otp.mod

    else

echo j/98+QEAAAACAAAAFAAAADYIAACN/3z5DwAAAFNFIExpbnV4IE1vZHVsZQIAAAATAAAAAQAAAAgAAAAAAAAACQAAAHZhdWx0LW90cAMAAAAxLjBAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAEAAAACgAAAAAAAAADAAAAAQAAAAEAAAAAAAAAdGNwX3NvY2tldAwAAAABAAAAbmFtZV9jb25uZWN0AwAAAAAAAAACAAAAAQAAAAEAAAAAAAAAZGlyBAAAAAEAAAByZWFkCAAAAAAAAAAEAAAAAgAAAAIAAAAAAAAAbG5rX2ZpbGUHAAAAAgAAAGdldGF0dHIEAAAAAQAAAHJlYWQEAAAAAAAAAAEAAAADAAAAAwAAAAAAAABmaWxlBgAAAAIAAABjcmVhdGUEAAAAAwAAAHJlYWQEAAAAAQAAAG9wZW4BAAAAAQAAAAgAAAABAAAAAAAAAG9iamVjdF9yQAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAEAAAABAAAAAsAAAADAAAAAQAAAAEAAAAAAAAAQAAAAAAAAAAAAAAAaHR0cF9wb3J0X3QJAAAAAQAAAAEAAAABAAAAAAAAAEAAAAAAAAAAAAAAAHZhcl9sb2dfdBAAAAAEAAAAAQAAAAEAAAAAAAAAQAAAAAAAAAAAAAAAY29udGFpbmVyX2ZpbGVfdAYAAAACAAAAAQAAAAEAAAAAAAAAQAAAAAAAAAAAAAAAc3NoZF90AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAQAAAAEAAAAAAAAAAAAAAAgAAAABAAAAAAAAAEAAAABAAAAAAQAAAAAAAAACAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAQAAAAAEAAAAAAAAAAQAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAQAAAAEAAAABAAAAAQAAAAAAAABAAAAAQAAAAAEAAAAAAAAAAgAAAAAAAABAAAAAAAAAAAAAAAAAAAAAQAAAAEAAAAABAAAAAAAAAAEAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAEAAAABAAAAAgAAAAEAAAAAAAAAQAAAAEAAAAABAAAAAAAAAAIAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAEAAAABAAAAAAQAAAAAAAAAEAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAABAAAAAwAAAAEAAAABAAAAAAAAAEAAAABAAAAAAQAAAAAAAAACAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAQAAAAAEAAAAAAAAACAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAQAAAAIAAAABAAAAAQAAAAAAAABAAAAAQAAAAAEAAAAAAAAAAgAAAAAAAABAAAAAAAAAAAAAAAAAAAAAQAAAAEAAAAABAAAAAAAAAAgAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAEAAAABAAAABAAAAAEAAAAAAAAAQAAAAEAAAAABAAAAAAAAAAIAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAEAAAABAAAAAAQAAAAAAAAAIAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAABAAAABAAAAAEAAAABAAAAAAAAAEAAAABAAAAAAQAAAAAAAAACAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAQAAAAAEAAAAAAAAACAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAQAAAAEAAAABAAAAAQAAAAAAAABAAAAAQAAAAAEAAAAAAAAAAgAAAAAAAABAAAAAAAAAAAAAAAAAAAAAQAAAAEAAAAABAAAAAAAAAAgAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAEAAAAEAAAAAgAAAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAABAAAAAQAAAAAEAAAAAAAAADwAAAAAAAABAAAAAAAAAAAAAAABAAAAAQAAAAAEAAAAAAAAADwAAAAAAAABAAAAAAAAAAAAAAABAAAAAAAAAAAAAAABAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAEAAAAQAAAAEAAAAABAAAAAAAAAAcAAAAAAAAAQAAAAEAAAAABAAAAAAAAAAEAAAAAAAAAQAAAAEAAAAABAAAAAAAAAAEAAAAAAAAAQAAAAEAAAAABAAAAAAAAAAMAAAAAAAAAQAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAoAAAB0Y3Bfc29ja2V0AQAAAAEAAAABAAAAAwAAAGRpcgEAAAABAAAAAQAAAAgAAABsbmtfZmlsZQEAAAABAAAAAQAAAAQAAABmaWxlAQAAAAEAAAABAAAAAQAAAAgAAABvYmplY3RfcgIAAAABAAAAAQAAAAQAAAALAAAAaHR0cF9wb3J0X3QBAAAAAQAAAAEAAAAJAAAAdmFyX2xvZ190AQAAAAEAAAABAAAAEAAAAGNvbnRhaW5lcl9maWxlX3QBAAAAAQAAAAEAAAAGAAAAc3NoZF90AQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACQ/3z5IwojIERpcmVjdG9yeSBwYXR0ZXJucyAoZGlyKQojCiMgUGFyYW1ldGVyczoKIyAxLiBkb21haW4gdHlwZQojIDIuIGNvbnRhaW5lciAoZGlyZWN0b3J5KSB0eXBlCiMgMy4gZGlyZWN0b3J5IHR5cGUKIwoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKIwojIFJlZ3VsYXIgZmlsZSBwYXR0ZXJucyAoZmlsZSkKIwojIFBhcmFtZXRlcnM6CiMgMS4gZG9tYWluIHR5cGUKIyAyLiBjb250YWluZXIgKGRpcmVjdG9yeSkgdHlwZQojIDMuIGZpbGUgdHlwZQojCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCiMKIyBTeW1ib2xpYyBsaW5rIHBhdHRlcm5zIChsbmtfZmlsZSkKIwojIFBhcmFtZXRlcnM6CiMgMS4gZG9tYWluIHR5cGUKIyAyLiBjb250YWluZXIgKGRpcmVjdG9yeSkgdHlwZQojIDMuIGZpbGUgdHlwZQojCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKIwojIChVbiluYW1lZCBQaXBlcy9GSUZPIHBhdHRlcm5zIChmaWZvX2ZpbGUpCiMKIyBQYXJhbWV0ZXJzOgojIDEuIGRvbWFpbiB0eXBlCiMgMi4gY29udGFpbmVyIChkaXJlY3RvcnkpIHR5cGUKIyAzLiBmaWxlIHR5cGUKIwoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCiMKIyAoVW4pbmFtZWQgc29ja2V0cyBwYXR0ZXJucyAoc29ja19maWxlKQojCiMgUGFyYW1ldGVyczoKIyAxLiBkb21haW4gdHlwZQojIDIuIGNvbnRhaW5lciAoZGlyZWN0b3J5KSB0eXBlCiMgMy4gZmlsZSB0eXBlCiMKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKIwojIEJsb2NrIGRldmljZSBub2RlIHBhdHRlcm5zIChibGtfZmlsZSkKIwojIFBhcmFtZXRlcnM6CiMgMS4gZG9tYWluIHR5cGUKIyAyLiBjb250YWluZXIgKGRpcmVjdG9yeSkgdHlwZQojIDMuIGZpbGUgdHlwZQojCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgojCiMgQ2hhcmFjdGVyIGRldmljZSBub2RlIHBhdHRlcm5zIChjaHJfZmlsZSkKIwojIFBhcmFtZXRlcnM6CiMgMS4gZG9tYWluIHR5cGUKIyAyLiBjb250YWluZXIgKGRpcmVjdG9yeSkgdHlwZQojIDMuIGZpbGUgdHlwZQojCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKIwojIEZpbGUgdHlwZV90cmFuc2l0aW9uIHBhdHRlcm5zCiMKIyBmaWxldHJhbnNfYWRkX3BhdHRlcm4oZG9tYWluLGRpcnR5cGUsbmV3dHlwZSxjbGFzcyhlcyksW2ZpbGVuYW1lXSkKIwoKCiMKIyBmaWxldHJhbnNfcGF0dGVybihkb21haW4sZGlydHlwZSxuZXd0eXBlLGNsYXNzKGVzKSxbZmlsZW5hbWVdKQojCgoKCiMKIyB1bml4IGRvbWFpbiBzb2NrZXQgcGF0dGVybnMKIwoKCgojIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjCiMgCiMgU3VwcG9ydCBtYWNyb3MgZm9yIHNldHMgb2Ygb2JqZWN0IGNsYXNzZXMgYW5kIHBlcm1pc3Npb25zCiMKIyBUaGlzIGZpbGUgc2hvdWxkIG9ubHkgaGF2ZSBvYmplY3QgY2xhc3MgYW5kIHBlcm1pc3Npb24gc2V0IG1hY3JvcyAtIHRoZXkKIyBjYW4gb25seSByZWZlcmVuY2Ugb2JqZWN0IGNsYXNzZXMgYW5kL29yIHBlcm1pc3Npb25zLgoKIwojIEFsbCBkaXJlY3RvcnkgYW5kIGZpbGUgY2xhc3NlcwojCgoKIwojIEFsbCBub24tZGlyZWN0b3J5IGZpbGUgY2xhc3Nlcy4KIwoKCiMKIyBOb24tZGV2aWNlIGZpbGUgY2xhc3Nlcy4KIwoKCiMKIyBEZXZpY2UgZmlsZSBjbGFzc2VzLgojCgoKIwojIEFsbCBzb2NrZXQgY2xhc3Nlcy4KIwoKCiMKIyBEYXRhZ3JhbSBzb2NrZXQgY2xhc3Nlcy4KIyAKCgojCiMgU3RyZWFtIHNvY2tldCBjbGFzc2VzLgojCgoKIwojIFVucHJpdmlsZWdlZCBzb2NrZXQgY2xhc3NlcyAoZXhjbHVkZSByYXdpcCwgbmV0bGluaywgcGFja2V0KS4KIwoKCiMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMKIyAKIyBNYWNyb3MgZm9yIHNldHMgb2YgcGVybWlzc2lvbnMKIwoKIwojIFBlcm1pc3Npb25zIHRvIG1vdW50IGFuZCB1bm1vdW50IGZpbGUgc3lzdGVtcy4KIwoKCiMKIyBQZXJtaXNzaW9ucyBmb3IgdXNpbmcgc29ja2V0cy4KIyAKCgojCiMgUGVybWlzc2lvbnMgZm9yIGNyZWF0aW5nIGFuZCB1c2luZyBzb2NrZXRzLgojIAoKCiMKIyBQZXJtaXNzaW9ucyBmb3IgdXNpbmcgc3RyZWFtIHNvY2tldHMuCiMgCgoKIwojIFBlcm1pc3Npb25zIGZvciBjcmVhdGluZyBhbmQgdXNpbmcgc3RyZWFtIHNvY2tldHMuCiMgCgoKIwojIFBlcm1pc3Npb25zIGZvciBjcmVhdGluZyBhbmQgdXNpbmcgc29ja2V0cy4KIyAKCgojCiMgUGVybWlzc2lvbnMgZm9yIGNyZWF0aW5nIGFuZCB1c2luZyBzb2NrZXRzLgojIAoKCgojCiMgUGVybWlzc2lvbnMgZm9yIGNyZWF0aW5nIGFuZCB1c2luZyBuZXRsaW5rIHNvY2tldHMuCiMgCgoKIwojIFBlcm1pc3Npb25zIGZvciB1c2luZyBuZXRsaW5rIHNvY2tldHMgZm9yIG9wZXJhdGlvbnMgdGhhdCBtb2RpZnkgc3RhdGUuCiMgCgoKIwojIFBlcm1pc3Npb25zIGZvciB1c2luZyBuZXRsaW5rIHNvY2tldHMgZm9yIG9wZXJhdGlvbnMgdGhhdCBvYnNlcnZlIHN0YXRlLgojIAoKCiMKIyBQZXJtaXNzaW9ucyBmb3Igc2VuZGluZyBhbGwgc2lnbmFscy4KIwoKCiMKIyBQZXJtaXNzaW9ucyBmb3Igc2VuZGluZyBhbmQgcmVjZWl2aW5nIG5ldHdvcmsgcGFja2V0cy4KIwoKCiMKIyBQZXJtaXNzaW9ucyBmb3IgdXNpbmcgU3lzdGVtIFYgSVBDCiMKCgoKCgoKCgoKCiMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMKIwojIE5ldyBwZXJtaXNzaW9uIHNldHMKIwoKIwojIERpcmVjdG9yeSAoZGlyKQojCgoKCgoKCgoKCgoKCgoKCiMKIyBSZWd1bGFyIGZpbGUgKGZpbGUpCiMKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgojCiMgU3ltYm9saWMgbGluayAobG5rX2ZpbGUpCiMKCgoKCgoKCgoKCgoKCgojCiMgKFVuKW5hbWVkIFBpcGVzL0ZJRk9zIChmaWZvX2ZpbGUpCiMKCgoKCgoKCgoKCgoKCgoKIwojIChVbiluYW1lZCBTb2NrZXRzIChzb2NrX2ZpbGUpCiMKCgoKCgoKCgoKCgoKCgojCiMgQmxvY2sgZGV2aWNlIG5vZGVzIChibGtfZmlsZSkKIwoKCgoKCgoKCgoKCgoKCgoKIwojIENoYXJhY3RlciBkZXZpY2Ugbm9kZXMgKGNocl9maWxlKQojCgoKCgoKCgoKCgoKCgoKCiMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMKIwojIFNwZWNpYWwgcGVybWlzc2lvbiBzZXRzCiMKCiMKIyBVc2UgKHJlYWQgYW5kIHdyaXRlKSB0ZXJtaW5hbHMKIwoKCgojCiMgU29ja2V0cwojCgoKCiMKIyBLZXlzCiMKCgojCiMgU2VydmljZQojCgoKCiMKIyBwZXJmX2V2ZW50CiMKCiMKIyBTcGVjaWZpZWQgZG9tYWluIHRyYW5zaXRpb24gcGF0dGVybnMKIwoKCiMgY29tcGF0aWJpbGl0eToKCgoKCiMKIyBBdXRvbWF0aWMgZG9tYWluIHRyYW5zaXRpb24gcGF0dGVybnMKIwoKCiMgY29tcGF0aWJpbGl0eToKCgoKCiMKIyBEeW5hbWljIHRyYW5zaXRpb24gcGF0dGVybgojCgoKIwojIE90aGVyIHByb2Nlc3MgcGVybWlzc2lvbnMKIwoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgojIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjCiMKIyBIZWxwZXIgbWFjcm9zCiMKCiMKIyBzaGlmdG4obnVtLGxpc3QuLi4pCiMKIyBzaGlmdCB0aGUgbGlzdCBudW0gdGltZXMKIwoKCiMKIyBpZm5kZWYoZXhwcix0cnVlX2Jsb2NrLGZhbHNlX2Jsb2NrKQojCiMgbTQgZG9lcyBub3QgaGF2ZSB0aGlzLgojCgoKIwojIF9fZW5kbGluZV9fCiMKIyBkdW1teSBtYWNybyB0byBpbnNlcnQgYSBuZXdsaW5lLiAgdXNlZCBmb3IgCiMgZXJycHJpbnQsIHNvIHRoZSBjbG9zZSBwYXJlbnRoZXNlcyBjYW4gYmUKIyBpbmRlbnRlZCBjb3JyZWN0bHkuCiMKCgojIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjCiMKIyByZWZwb2x3YXJuKG1lc3NhZ2UpCiMKIyBwcmludCBhIHdhcm5pbmcgbWVzc2FnZQojCgoKIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIwojCiMgcmVmcG9sZXJyKG1lc3NhZ2UpCiMKIyBwcmludCBhbiBlcnJvciBtZXNzYWdlLiAgZG9lcyBub3QKIyBtYWtlIGFueXRoaW5nIGZhaWwuCiMKCgojIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjCiMKIyBnZW5fdXNlcih1c2VybmFtZSwgcHJlZml4LCByb2xlX3NldCwgbWxzX2RlZmF1bHRsZXZlbCwgbWxzX3JhbmdlLCBbbWNzX2NhdGVnb3JpZXNdKQojCgoKIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIwojCiMgZ2VuX2NvbnRleHQoY29udGV4dCxtbHNfc2Vuc2l0aXZpdHksW21jc19jYXRlZ29yaWVzXSkKIwoKIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIwojCiMgY2FuX2V4ZWMoZG9tYWluLGV4ZWN1dGFibGUpCiMKCgojIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjCiMKIyBnZW5fYm9vbChuYW1lLGRlZmF1bHRfdmFsdWUpCiMKCiMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMKIwojIGdlbl9jYXRzKE4pCiMKIyBkZWNsYXJlcyBjYXRlZ29yZXMgYzAgdG8gYyhOLTEpCiMKCgoKCiMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMKIwojIGdlbl9zZW5zKE4pCiMKIyBkZWNsYXJlcyBzZW5zaXRpdml0ZXMgczAgdG8gcyhOLTEpIHdpdGggZG9taW5hbmNlCiMgaW4gaW5jcmVhc2luZyBudW1lcmljIG9yZGVyIHdpdGggczAgbG93ZXN0LCBzKE4tMSkgaGlnaGVzdAojCgoKCgoKCiMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMKIwojIGdlbl9sZXZlbHMoTixNKQojCiMgbGV2ZWxzIGZyb20gczAgdG8gKE4tMSkgd2l0aCBjYXRlZ29yaWVzIGMwIHRvIChNLTEpCiMKCgoKCiMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMKIwojIEJhc2ljIGxldmVsIG5hbWVzIGZvciBzeXN0ZW0gbG93IGFuZCBoaWdoCiMKCgoKCgojIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjCiMKIyBNYWNyb3MgZm9yIHN3aXRjaGluZyBiZXR3ZWVuIHNvdXJjZSBwb2xpY3kKIyBhbmQgbG9hZGFibGUgcG9saWN5IG1vZHVsZSBzdXBwb3J0CiMKCiMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIwojCiMgRm9yIGFkZGluZyB0aGUgbW9kdWxlIHN0YXRlbWVudAojCgoKIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjCiMKIyBGb3IgdXNlIGluIGludGVyZmFjZXMsIHRvIG9wdGlvbmFsbHkgaW5zZXJ0IGEgcmVxdWlyZSBibG9jawojCgoKIyBoZWxwZXIgZnVuY3Rpb24sIHNpbmNlIG00IHdvbnQgZXhwYW5kIG1hY3JvcwojIGlmIGEgbGluZSBpcyBhIGNvbW1lbnQgKCMpOgoKIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjCiMKIyBJbiB0aGUgZnV0dXJlIGludGVyZmFjZXMgc2hvdWxkIGJlIGluIGxvYWRhYmxlIG1vZHVsZXMKIwojIHRlbXBsYXRlKG5hbWUscnVsZXMpCiMKCgojIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMKIwojIEluIHRoZSBmdXR1cmUgaW50ZXJmYWNlcyBzaG91bGQgYmUgaW4gbG9hZGFibGUgbW9kdWxlcwojCiMgaW50ZXJmYWNlKG5hbWUscnVsZXMpCiMKCgoKCiMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIwojCiMgT3B0aW9uYWwgcG9saWN5IGhhbmRsaW5nCiMKCgojIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMKIwojIERldGVybWluZSBpZiB3ZSBzaG91bGQgdXNlIHRoZSBkZWZhdWx0CiMgdHVuYWJsZSB2YWx1ZSBhcyBzcGVjaWZpZWQgYnkgdGhlIHBvbGljeQojIG9yIGlmIHRoZSBvdmVycmlkZSB2YWx1ZSBzaG91bGQgYmUgdXNlZAojCgoKIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjCiMKIyBFeHRyYWN0IGJvb2xlYW5zIG91dCBvZiBhbiBleHByZXNzaW9uLgojIFRoaXMgbmVlZHMgdG8gYmUgcmV3b3JrZWQgc28gZXhwcmVzc2lvbnMKIyB3aXRoIHBhcmVudGhlc2VzIGNhbiB3b3JrLgoKCgojIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMKIwojIFR1bmFibGUgZGVjbGFyYXRpb24KIwoKCiMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIwojCiMgVHVuYWJsZSBwb2xpY3kgaGFuZGxpbmcKIwoK  | base64 -d > /etc/vault-ssh-helper.d/vault-otp.pp

        fi
    semodule -i /etc/vault-ssh-helper.d/vault-otp.pp
fi

systemctl reload sshd
