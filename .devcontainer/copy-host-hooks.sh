#!/usr/bin/env bash
# initializeCommand: runs on the host before the container is created. Copies
# the hooks the host's core.hooksPath names into .devcontainer/host-git-hooks
# at the top of the work tree, which git ignores, so the container can run
# them; lifecycle.sh points the container's core.hooksPath there. With no
# core.hooksPath on the host, any old copy is removed and nothing is copied,
# and the container runs petstore's hooks alone and says so.
#
# The copy sits three levels below /workspaces, so a hook that finds toolbox as
# its directory's ../../../toolbox, as dotfiles' voice-tells does, finds the
# image's /workspaces/toolbox.
set -euo pipefail

top=$(git rev-parse --show-toplevel)
dest="$top/.devcontainer/host-git-hooks"

# git exits 1 when the key is unset; anything else is a broken config.
rc=0
src=$(git config --type=path --get core.hooksPath) || rc=$?
if [ "$rc" -ne 0 ] && [ "$rc" -ne 1 ]; then
    echo "refused: reading the host's core.hooksPath exited $rc" >&2
    exit 1
fi
if [ -n "$src" ]; then
    case "$src" in
        /*) ;;
        *) src="$top/$src" ;;
    esac
    if [ ! -d "$src" ]; then
        echo "refused: the host's core.hooksPath, $src, is not a directory" >&2
        exit 1
    fi
fi

if [ -L "$dest" ]; then
    echo "refused: $dest is a symlink" >&2
    exit 1
fi
if [ -d "$dest" ]; then
    find "${dest:?}" -mindepth 1 -delete
    rmdir "${dest:?}"
fi

if [ -z "$src" ]; then
    echo "host core.hooksPath is unset: no global hooks copied"
    exit 0
fi
mkdir -p "$dest"
cp -RL "$src/." "$dest/"
echo "copied the host's global hooks from $src to $dest"
