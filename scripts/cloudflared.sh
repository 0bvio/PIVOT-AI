#!/usr/bin/env sh
# scripts/cloudflared.sh
# Helper wrapper to run cloudflared via docker-compose so CLI commands (login, create, route, run)
# work even if cloudflared isn't installed on the host.

set -eu

COMPOSE_FILES="-f docker-compose.yml -f docker-compose.override.yml"
DC="sudo docker compose ${COMPOSE_FILES}"

usage() {
  cat <<EOF
Usage: $0 <command> [args]
Commands:
  login                    Run 'cloudflared tunnel login' (opens browser on host)
  create <name>            Create a named tunnel (writes credentials JSON into ./cloudflared)
  route-dns <uuid> <host>  Route DNS for the tunnel to the given hostname (chat.0bv.io)
  run                      Run the tunnel using config.yml (delegates to 'tunnel run')
  run-detached             Start the cloudflared service in the background via docker-compose
  version                  Print cloudflared version

Examples:
  # Open browser to authenticate and download credentials (interactive):
  ./scripts/cloudflared.sh login

  # Create a tunnel named 'chat-0bv-io':
  ./scripts/cloudflared.sh create chat-0bv-io

  # Route DNS for the created tunnel UUID to chat.0bv.io (after create):
  ./scripts/cloudflared.sh route-dns <TUNNEL_UUID> chat.0bv.io

  # Run the tunnel using config (expects cloudflared/config.yml and credentials present):
  ./scripts/cloudflared.sh run

  # Start background cloudflared service (docker-compose)
  ./scripts/cloudflared.sh run-detached

EOF
}

if [ $# -lt 1 ]; then
  usage
  exit 1
fi

COMMAND=$1
shift

case "$COMMAND" in
  login)
    # This will open a URL for you to authorize; it writes credentials to ~/.cloudflared by default.
    # We run it in the compose service network so the created credentials can be copied to ./cloudflared
    echo "Running cloudflared tunnel login (interactive)..."
    ${DC} run --rm cloudflared tunnel login
    ;;

  create)
    if [ $# -ne 1 ]; then
      echo "create requires a tunnel name" >&2
      usage
      exit 2
    fi
    NAME=$1
    echo "Creating tunnel named: ${NAME}"
    ${DC} run --rm cloudflared tunnel create "${NAME}"
    ;;

  route-dns)
    if [ $# -ne 2 ]; then
      echo "route-dns requires <TUNNEL_UUID> <HOST>" >&2
      usage
      exit 2
    fi
    UUID=$1
    HOST=$2
    echo "Routing DNS ${HOST} to tunnel ${UUID}"
    ${DC} run --rm cloudflared tunnel route dns "${UUID}" "${HOST}"
    ;;

  run)
    echo "Running tunnel using docker-compose (foreground). Ensure ./cloudflared/config.yml exists."
    ${DC} run --rm cloudflared tunnel run
    ;;

  run-detached)
    echo "Starting cloudflared via docker-compose up -d"
    sudo docker compose -f docker-compose.yml -f docker-compose.override.yml up -d cloudflared
    ;;

  version)
    ${DC} run --rm cloudflared --version
    ;;

  *)
    echo "Unknown command: $COMMAND" >&2
    usage
    exit 2
    ;;

esac

