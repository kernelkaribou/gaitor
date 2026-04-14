#!/bin/bash
set -e

# Default PUID and PGID to 1000 if not set (non-root)
PUID=${PUID:-1000}
PGID=${PGID:-1000}

# If running as root, skip user creation
if [ "$PUID" = "0" ] && [ "$PGID" = "0" ]; then
    exec "$@"
fi

# Create app user if it doesn't exist
if ! id -u appuser > /dev/null 2>&1; then
    # Use existing group if GID is taken, otherwise create one
    if getent group "$PGID" > /dev/null 2>&1; then
        EXISTING_GROUP=$(getent group "$PGID" | cut -d: -f1)
        useradd -u "$PUID" -g "$EXISTING_GROUP" -d /app -s /bin/bash appuser
    else
        groupadd -g "$PGID" appgroup
        useradd -u "$PUID" -g "$PGID" -d /app -s /bin/bash appuser
    fi
fi

# Update existing user's UID/GID if they differ
CURRENT_UID=$(id -u appuser 2>/dev/null || echo 0)
CURRENT_GID=$(id -g appuser 2>/dev/null || echo 0)

if [ "$CURRENT_UID" != "$PUID" ] || [ "$CURRENT_GID" != "$PGID" ]; then
    groupmod -g "$PGID" appgroup 2>/dev/null || true
    usermod -u "$PUID" -g "$PGID" appuser 2>/dev/null || true
fi

# Set ownership of app directory (recursive) and mount points (non-recursive)
chown -R "$PUID:$PGID" /app 2>/dev/null || true
chown "$PUID:$PGID" /library 2>/dev/null || true
chown "$PUID:$PGID" /hosts 2>/dev/null || true

# Switch to app user and execute the command
exec gosu appuser "$@"
