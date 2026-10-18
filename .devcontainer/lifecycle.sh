#!/usr/bin/env bash
# The container's lifecycle commands, in the workspace folder.
#
#   lifecycle.sh create   postCreateCommand: hooks path, uv sync, just hooks
#   lifecycle.sh attach   postAttachCommand: hooks path only
#
# The hooks path is set again on every attach because the Dev Containers
# client copies the host's git config into the container, and that copy names
# the host's hooks directory, which does not exist here. Every failure stops
# the command and shows in its output; nothing falls back silently.
set -euo pipefail

mode=${1:?create or attach}
hooks="$PWD/.devcontainer/host-git-hooks"

# It rewrites the global git config, which on a host is the host's own and
# carries its hooks path, so it runs only inside a container.
if [ ! -e /.dockerenv ] && [ ! -e /run/.containerenv ]; then
    echo "refused: lifecycle.sh changes the global git config and runs only inside the devcontainer" >&2
    exit 1
fi

loud() {
    printf '\n*** %s\n\n' "$*" >&2
}

# Unset core.hooksPath in each global file, then set it once where there is a
# copy to point at. git exits 5 from --unset-all when there was nothing to unset.
hooks_path() {
    local f rc
    for f in "$HOME/.gitconfig" "${XDG_CONFIG_HOME:-$HOME/.config}/git/config"; do
        [ -f "$f" ] || continue
        rc=0
        git config --file "$f" --unset-all core.hooksPath || rc=$?
        if [ "$rc" -ne 0 ] && [ "$rc" -ne 5 ]; then
            echo "refused: could not unset core.hooksPath in $f" >&2
            exit 1
        fi
    done
    local want=""
    if [ -d "$hooks" ]; then
        if [ ! -x "$hooks/pre-commit" ] || [ ! -x "$hooks/commit-msg" ]; then
            echo "refused: $hooks, the copy of the host's hooks, lacks an executable pre-commit or commit-msg" >&2
            exit 1
        fi
        git config --global core.hooksPath "$hooks"
        want=$hooks
        echo "core.hooksPath is $hooks, the host's global hooks"
    else
        loud "The host has no global core.hooksPath to copy, so no global hook runs on a commit in this container. Only petstore's own hooks do."
    fi
    local now
    rc=0
    now=$(git config --get core.hooksPath) || rc=$?
    if [ "$rc" -ne 0 ] && [ "$rc" -ne 1 ]; then
        echo "refused: git config --get core.hooksPath exited $rc" >&2
        exit 1
    fi
    if [ "$now" != "$want" ]; then
        echo "refused: core.hooksPath reads '$now', not '$want'" >&2
        exit 1
    fi
}

case "$mode" in
    create)
        hooks_path
        uv sync --frozen
        if git rev-parse --git-dir >/dev/null 2>&1; then
            uv run just hooks
        else
            loud "No git metadata in the workspace, so no hooks are installed."
        fi
        ;;
    attach)
        hooks_path
        ;;
    *)
        echo "usage: lifecycle.sh create|attach" >&2
        exit 2
        ;;
esac
