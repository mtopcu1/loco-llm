#!/usr/bin/env bash
# Wrapper for scripts/install.sh (git-clone distribution).
# End users: curl -fsSL https://raw.githubusercontent.com/mtopcu1/loco-llm/main/scripts/install.sh | bash
exec "$(dirname "$0")/scripts/install.sh" "$@"
