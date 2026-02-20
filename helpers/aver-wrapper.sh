#!/bin/bash
# User installs this in their personal bin directory
# Then they can run 'aver' from anywhere in any repo

# Find the git repo root
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"

if [[ -z "$REPO_ROOT" ]]; then
    if [[ -f "${HOME}/bin/aver.py" ]]; then
        exec "python3 ~/bin/aver.py" "$@"
    else
	echo "aver: not found (not in a git repo)"
        exit 1
    fi
fi

# Delegate to the repo's incident wrapper
if [[ -f "$REPO_ROOT/bin/aver" ]]; then
    exec python3 "$REPO_ROOT/bin/aver" "$@"
elif [[ -f "$REPO_ROOT/bin/aver.py" ]]; then
    exec python3 "$REPO_ROOT/bin/aver.py" "$@"
elif [[ -f "$REPO_ROOT/aver" ]]; then
    exec python3 "$REPO_ROOT/aver" "$@"
elif [[ -f "$REPO_ROOT/aver.py" ]]; then
    exec python3 "$REPO_ROOT/aver.py" "$@"
elif [[ -f "${HOME}/bin/aver.py" ]]; then
    exec python3 "${HOME}/bin/aver.py" "$@"
else
    echo "aver: not found (checked git repo [${REPO_ROOT}, ${REPO_ROOT}/bin] and ${HOME}/bin)"
    exit 1
fi
