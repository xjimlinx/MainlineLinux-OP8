#!/usr/bin/env bash
set -euo pipefail

pkg=${1:?usage: install-wps365-arm64.sh /path/to/wps-office_arm64.deb}
test -f "$pkg"

work=$(mktemp -d /tmp/wps365-install.XXXXXX)
cleanup() { rm -rf "$work"; }
trap cleanup EXIT

printf '%s\n' '[wps365] extracting data archive'
ar p "$pkg" data.tar.xz | tar -xJf - -C /

printf '%s\n' '[wps365] extracting vendor post-install script'
ar p "$pkg" control.tar.gz | tar -xzOf - ./postinst > "$work/postinst"
chmod 0755 "$work/postinst"

printf '%s\n' '[wps365] configuring desktop entries, fonts and MIME types'
WPS_INSTALL_LOG=1 timeout 300 "$work/postinst" configure

update-mime-database /usr/share/mime >/dev/null 2>&1 || true
update-desktop-database /usr/share/applications >/dev/null 2>&1 || true

printf '%s\n' '[wps365] verification'
file /opt/kingsoft/wps-office/office6/wps
test -x /usr/bin/wps
test -f /usr/share/applications/wps-office-wps.desktop
printf '%s\n' '[wps365] install complete'
