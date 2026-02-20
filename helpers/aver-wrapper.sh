#!/bin/bash
# Aver Wrapper: Ensures the project-sanctioned engine is used.
# Installation: Copy to ~/bin/aver and chmod +x

# Find the git repo root
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"

# If not in a git repo, fall back to the user's home bin
if [[ -z "$REPO_ROOT" ]]; then
    if [[ -f "${HOME}/bin/aver.py" ]]; then
        export PYTHONPATH="${HOME}/bin"
        exec python3 "${HOME}/bin/aver.py" "$@"
    else
        echo "aver: not found (not in a git repo and no global ~/bin/aver.py found)"
        exit 1
    fi
fi

# Search Order: 
# 1. repo/bin/aver 
# 2. repo/bin/aver.py 
# 3. repo/aver 
# 4. repo/aver.py
# 5. ~/bin/aver.py (Global Fallback)

if [[ -f "$REPO_ROOT/bin/aver" ]]; then
    SCRIPT="$REPO_ROOT/bin/aver"
elif [[ -f "$REPO_ROOT/bin/aver.py" ]]; then
    SCRIPT="$REPO_ROOT/bin/aver.py"
elif [[ -f "$REPO_ROOT/aver" ]]; then
    SCRIPT="$REPO_ROOT/aver"
elif [[ -f "$REPO_ROOT/aver.py" ]]; then
    SCRIPT="$REPO_ROOT/aver.py"
elif [[ -f "${HOME}/bin/aver.py" ]]; then
    SCRIPT="${HOME}/bin/aver.py"
else
    echo "aver: engine not found."
    echo "Checked: ${REPO_ROOT}/[bin/], and ${HOME}/bin/aver.py"
    exit 1
fi

# Set PYTHONPATH to the script's directory so local imports work
export PYTHONPATH="$(dirname "$SCRIPT"):$PYTHONPATH"
exec python3 "$SCRIPT" "$@"
