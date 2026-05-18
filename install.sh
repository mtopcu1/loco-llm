#!/usr/bin/env bash
echo "This installer moved to scripts/install-dev.sh for contributors."
echo "For end users: curl -fsSL https://raw.githubusercontent.com/mtopcu1/local-llm-scaffold/main/scripts/install.sh | bash"
exec "$(dirname "$0")/scripts/install-dev.sh"
