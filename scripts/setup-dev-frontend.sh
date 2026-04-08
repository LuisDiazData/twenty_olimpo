#!/usr/bin/env bash
# setup-dev-frontend.sh
# Installs nvm + Node 24 and starts the twenty-front dev server
# pointing to the running Docker backend at http://localhost:3000
#
# Usage: bash scripts/setup-dev-frontend.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Setting up frontend dev environment ==="

# 1. Install nvm if not present
if [ ! -d "$HOME/.nvm" ]; then
  echo "Installing nvm..."
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
fi

# 2. Load nvm
export NVM_DIR="$HOME/.nvm"
# shellcheck disable=SC1091
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"

# 3. Install required Node version
NODE_VERSION=$(cat "$PROJECT_ROOT/.nvmrc")
echo "Installing Node $NODE_VERSION..."
nvm install "$NODE_VERSION"
nvm use "$NODE_VERSION"

echo "Node: $(node --version)"

# 4. Enable corepack (for yarn)
corepack enable

# 5. Install dependencies
cd "$PROJECT_ROOT"
echo "Installing dependencies (this may take a few minutes)..."
yarn install --immutable

# 6. Start the dev server
echo ""
echo "=== Starting frontend dev server on http://localhost:3001 ==="
echo "Backend: http://localhost:3000 (Docker)"
echo ""
REACT_APP_SERVER_BASE_URL=http://localhost:3000 npx nx start twenty-front
