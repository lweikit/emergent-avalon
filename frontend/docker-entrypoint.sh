#!/bin/sh
set -e

# Substitute only BACKEND_HOST in the nginx template (preserves $uri, $host, etc.)
envsubst '${BACKEND_HOST}' < /etc/nginx/avalon.conf.template > /etc/nginx/conf.d/avalon.conf

exec "$@"
