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
    groupadd -g "$PGID" appgroup
    useradd -u "$PUID" -g "$PGID" -d /app -s /bin/bash appuser
fi

# Update existing user's UID/GID if they differ
CURRENT_UID=$(id -u appuser 2>/dev/null || echo 0)
CURRENT_GID=$(id -g appuser 2>/dev/null || echo 0)

if [ "$CURRENT_UID" != "$PUID" ] || [ "$CURRENT_GID" != "$PGID" ]; then
    groupmod -g "$PGID" appgroup 2>/dev/null || true
    usermod -u "$PUID" -g "$PGID" appuser 2>/dev/null || true
fi

# Set ownership of app and data dirs (ignore errors for read-only mounts)
for dir in /app /library /targets; do
    if [ "$(stat -c %u "$dir" 2>/dev/null)" != "$PUID" ]; then
        chown -R "$PUID:$PGID" "$dir" 2>/dev/null || true
    fi
done

# Switch to app user and execute the command
exec gosu appuser "$@"
