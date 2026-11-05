#!/usr/bin/env bash
# Baseline Ubuntu host hardening for the USIPHU OCI pilot.
set -Eeuo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo." >&2
  exit 1
fi
: "${USIPHU_SSH_CIDR:?Set USIPHU_SSH_CIDR to your current administrator public IP/CIDR before running}"
if [[ "$USIPHU_SSH_CIDR" == "0.0.0.0/0" || "$USIPHU_SSH_CIDR" == "::/0" ]]; then
  echo "Refusing to expose SSH to the entire internet." >&2
  exit 1
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y ufw fail2ban unattended-upgrades

# Preserve the current SSH session by allowing the supplied administrator CIDR
# before enabling UFW. OCI NSG/security-list rules must independently match.
ufw default deny incoming
ufw default allow outgoing
ufw allow from "$USIPHU_SSH_CIDR" to any port 22 proto tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

systemctl enable --now fail2ban
systemctl enable --now unattended-upgrades

cat <<'NOTICE'
Baseline host hardening applied.
Still required:
- Restrict OCI NSG/security-list TCP 22 to the same administrator CIDR.
- Permit only TCP 80/443 publicly; never expose 8501, database ports or Docker API.
- Use SSH keys, disable password/root SSH login after verifying key access.
- Keep Docker and the OS patched; review fail2ban and unattended-upgrades status.
NOTICE
