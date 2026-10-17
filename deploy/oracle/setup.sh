#!/usr/bin/env bash
# One-time setup of the Qapital API on a fresh Oracle Cloud Ubuntu VM (Ampere A1). Run it from the cloned repo:
#   git clone https://github.com/sameeksha15/Qapital.git && bash Qapital/deploy/oracle/setup.sh
# It installs Docker, opens ports 80 and 443, writes deploy/oracle/.env (private settings), starts the API behind
# Caddy (HTTPS), and creates an SSH key that GitHub Actions uses to redeploy after each merge to main.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
env_file="$here/.env"

echo "== 1/5 Docker"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
fi

echo "== 2/5 Firewall: allow web traffic (Oracle's Ubuntu images block everything but SSH)"
for port in 443 80; do
  if ! sudo iptables -C INPUT -p tcp --dport "$port" -m state --state NEW -j ACCEPT 2>/dev/null; then
    sudo iptables -I INPUT 6 -p tcp --dport "$port" -m state --state NEW -j ACCEPT
  fi
done
if command -v netfilter-persistent >/dev/null 2>&1; then sudo netfilter-persistent save; fi

echo "== 3/5 Settings"
ip="$(curl -fsS https://api.ipify.org)"
host="${ip//./-}.sslip.io"
if [ -f "$env_file" ]; then
  echo "Keeping the existing $env_file (edit it to change settings)."
else
  read -rsp "Paste the Neon connection string (it won't be shown): " database_url; echo
  read -rp "Website address, e.g. https://qapital.vercel.app (leave empty if you don't have it yet): " site
  umask 077
  cat > "$env_file" <<EOF
API_HOST=$host
DATABASE_URL=$database_url
QAPITAL_SNAPSHOT_REPO=sameeksha15/Qapital
QAPITAL_CORS_ORIGINS=${site:-http://localhost:5173}
EOF
fi

echo "== 4/5 Start the API (the first build takes a few minutes)"
sudo docker compose -f "$here/compose.yml" up -d --build

echo "== 5/5 Deploy key for GitHub Actions"
key="$HOME/.ssh/qapital_deploy"
if [ ! -f "$key" ]; then
  ssh-keygen -q -t ed25519 -N "" -C "qapital-deploy" -f "$key"
  cat "$key.pub" >> "$HOME/.ssh/authorized_keys"
fi

cat <<EOF

Done. The API will be at:   https://$host
(It answers once the build has finished and the price snapshot is downloaded: try https://$host/health)

For automatic deploys, add these in GitHub -> Settings -> Secrets and variables -> Actions:
  secret    ORACLE_SSH_KEY  = everything printed below, including the BEGIN and END lines
  variable  ORACLE_HOST     = $ip
  variable  ORACLE_USER     = $(whoami)
  variable  API_HOST        = $host
Repo folder on this VM: $repo

----- private key (copy it into the GitHub secret, then clear your terminal) -----
EOF
cat "$key"
