#!/usr/bin/env sh
# scripts/cloudflared.sh
# Helper wrapper to run cloudflared via Docker so CLI commands (login, create, route, run)
# work even if cloudflared isn't installed on the host.

set -eu

# Compose files used by this project
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.override.yml"

# Detect docker executable (docker or podman)
if command -v docker >/dev/null 2>&1; then
  DOCKER_CLI=docker
elif command -v podman >/dev/null 2>&1; then
  DOCKER_CLI=podman
else
  echo "ERROR: docker or podman not found on PATH. Install Docker or Podman to continue." >&2
  exit 3
fi

# Detect compose form: 'docker compose' (v2+) or legacy 'docker-compose'
if $DOCKER_CLI compose version >/dev/null 2>&1; then
  DC="$DOCKER_CLI compose $COMPOSE_FILES"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose $COMPOSE_FILES"
else
  DC=""
fi

usage() {
  cat <<EOF
Usage: $0 <command> [args]
Commands:
  login                    Run 'cloudflared tunnel login' (interactive)
  create <name>            Create a named tunnel (writes credentials JSON into your host ~/.cloudflared)
  route-dns <uuid> <host>  Route DNS for the tunnel to the given hostname (chat.0bv.io)
  run                      Run the tunnel using config.yml (delegates to 'tunnel run')
  run-detached             Start the cloudflared service in the background via docker-compose
  version                  Print cloudflared version

Examples:
  ./scripts/cloudflared.sh version
  ./scripts/cloudflared.sh login
  ./scripts/cloudflared.sh create chat-0bv-io
  ./scripts/cloudflared.sh route-dns <TUNNEL_UUID> chat.0bv.io
  ./scripts/cloudflared.sh run-detached

Note: the script prefers to use 'docker compose' or 'docker-compose' from your host. If those are not available,
it can still run the cloudflared image directly with 'docker run' (fallback) but that may require additional flags
or host networking so cloudflared can reach the Open WebUI.
EOF
}

if [ $# -lt 1 ]; then
  usage
  exit 1
fi

COMMAND=$1
shift

# Helper to run a cloudflared command via compose (if available)
run_via_compose() {
  if [ -n "$DC" ]; then
    # shellcheck disable=SC2086
    $DC run --rm cloudflared "$@"
    return $?
  fi
  return 2
}

# Fallback: run cloudflared image directly with docker run --rm
run_via_docker_run() {
  # Use host networking so the container can reach services bound to host ports (e.g., open-webui at localhost:3000)
  # This is Linux-specific; warn if not Linux.
  if [ "$(uname -s)" != "Linux" ]; then
    echo "ERROR: Fallback docker run uses --network host which works on Linux only. Install docker compose or cloudflared CLI." >&2
    return 4
  fi

  HOST_PWD=$(pwd)
  # Ensure host ~/.cloudflared exists so login writes the cert there
  HOME_DIR=${HOME:-$(getent passwd $(id -u) | cut -d: -f6)}
  ORIG_DIR="$HOME_DIR/.cloudflared"
  if [ ! -d "$ORIG_DIR" ]; then
    mkdir -p "$ORIG_DIR"
    echo "Created $ORIG_DIR to store cloudflared origin certs"
  fi

  # Mount host origin cert dir into container's home (the cloudflared image runs as nonroot user with home /home/nonroot)
  ORIG_MOUNT_OPTS="-v \"$ORIG_DIR:/home/nonroot/.cloudflared:rw\""

  # mount ./cloudflared into /etc/cloudflared and run the image with provided args
  # shellcheck disable=SC2086
  # Run the container as the host user so it can write to the mounted ~/.cloudflared
  HOST_UID=$(id -u)
  HOST_GID=$(id -g)
  $DOCKER_CLI run --rm --network host -u "$HOST_UID:$HOST_GID" -v "$HOST_PWD/cloudflared:/etc/cloudflared:rw" -v "$ORIG_DIR:/home/nonroot/.cloudflared:rw" cloudflare/cloudflared "$@"
}

case "$COMMAND" in
  login)
    echo "Attempting interactive login via cloudflared..."
    if run_via_compose tunnel login; then
      exit 0
    fi
    echo "Compose not available; falling back to docker run (interactive)..."
    if run_via_docker_run tunnel login; then
      exit 0
    fi
    echo "ERROR: Could not run cloudflared login via docker. Install docker compose or cloudflared locally." >&2
    exit 5
    ;;

  create)
    if [ $# -ne 1 ]; then
      echo "create requires a tunnel name" >&2
      usage
      exit 2
    fi
    NAME=$1
    echo "Creating tunnel named: ${NAME} (this writes credentials to your host ~/.cloudflared)"
    if run_via_compose tunnel create "${NAME}"; then
      exit 0
    fi
    echo "Compose not available; falling back to docker run..."
    if run_via_docker_run tunnel create "${NAME}"; then
      exit 0
    fi
    echo "ERROR: Could not create tunnel via docker. Install docker compose or cloudflared locally." >&2
    exit 6
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
    if run_via_compose tunnel route dns "${UUID}" "${HOST}"; then
      exit 0
    fi
    echo "Compose not available; falling back to docker run..."
    if run_via_docker_run tunnel route dns "${UUID}" "${HOST}"; then
      exit 0
    fi
    echo "ERROR: Could not route DNS via docker. Install docker compose or cloudflared locally." >&2
    exit 7
    ;;

  run)
    echo "Running tunnel in foreground using compose (or docker run fallback). Ensure ./cloudflared/config.yml exists."
    if run_via_compose tunnel run; then
      exit 0
    fi
    echo "Compose not available; falling back to docker run (host network)."
    if run_via_docker_run tunnel run; then
      exit 0
    fi
    echo "ERROR: Could not run tunnel." >&2
    exit 8
    ;;

  run-detached)
    echo "Starting cloudflared via docker compose up -d (if compose available)."
    if [ -n "$DC" ]; then
      # shellcheck disable=SC2086
      $DC up -d cloudflared
      exit $?
    fi
    echo "Compose not available. You can run the tunnel in detached mode using docker run with host networking:" >&2
    echo "  docker run -d --network host -v \\"$(pwd)/cloudflared:/etc/cloudflared:rw\\" --name cloudflared cloudflare/cloudflared tunnel run" >&2
    exit 9
    ;;

  version)
    if run_via_compose --version; then
      exit 0
    fi
    if run_via_docker_run --version; then
      exit 0
    fi
    echo "ERROR: Could not determine cloudflared version; install docker compose or cloudflared locally." >&2
    exit 10
    ;;

  *)
    echo "Unknown command: $COMMAND" >&2
    usage
    exit 2
    ;;

esac
