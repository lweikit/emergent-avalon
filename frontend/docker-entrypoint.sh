#!/bin/sh
set -e

# Generate runtime env.js for optional cloud deployment
cat <<EOT > /app/public/env.js
window._env_ = {
  REACT_APP_BACKEND_URL: "${REACT_APP_BACKEND_URL}"
};
EOT

exec "$@"
