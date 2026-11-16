#!/bin/sh

# A credential that is not set is read from the Docker secret of its name in lower case, such as
# /run/secrets/secret_key for SECRET_KEY, so that it is not kept in the service definition.
for name in SECRET_KEY ORCID_CLIENT_ID ORCID_CLIENT_SECRET GITHUB_TOKEN; do
    file="/run/secrets/$(echo "$name" | tr 'A-Z' 'a-z')"
    if [ -z "$(printenv "$name")" ] && [ -r "$file" ]; then
        export "$name=$(cat "$file")"
    fi
done

# The platform does not start on a database of another release
python -m linkeddata check || exit 1

# With PLATFORM_LAUNCH=1, the first start launches the platform: it imports all sources into a new database.
# The launch is made in a staging folder, which becomes PLATFORM_STATE only at its end. A launch that is stopped,
# such as by an update of the image, is made again at the next start, and a database in PLATFORM_STATE is always
# a finished launch. A kept database is never launched again.
state="${PLATFORM_STATE:-instance}"
if [ "${PLATFORM_LAUNCH:-}" = "1" ] && [ ! -e "$state/platform.sqlite" ]; then
    staging="$state.launching"
    rm -rf "$staging"
    echo "No database in $state: launching the platform in $staging"
    PLATFORM_STATE="$staging" python -m linkeddata launch
    status=$?
    # Status 3 is a launch that ended without some sources, which it lists. A launch that failed, such as with an
    # error, or that imported no record, such as without a network, is made again at the next start, five minutes
    # later, so that the sources are not asked again and again.
    imported=$(python -c 'import sqlite3, sys; print(sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True).execute("SELECT count(*) FROM records WHERE source != ?", ("platform",)).fetchone()[0])' "$staging/platform.sqlite" 2>/dev/null || echo 0)
    if { [ "$status" -ne 0 ] && [ "$status" -ne 3 ]; } || [ "$imported" -eq 0 ]; then
        echo "The launch failed (status $status, $imported records imported); it is made again at the next start" >&2
        sleep 300
        exit 1
    fi
    if [ "$status" -eq 3 ]; then
        echo "The launch ended without the sources listed above; the platform starts with its $imported records" >&2
    fi
    if [ -e "$state" ]; then
        mv "$state" "$state.before-launch-$(date -u +%Y%m%dT%H%M%SZ)"
    fi
    mv "$staging" "$state" || exit 1
    echo "Launched: $imported records in $state/platform.sqlite"
fi

# Start Flask app
exec gunicorn --bind 0.0.0.0:5050 --workers 1 --threads 8 --timeout 120 app:app
