#!/bin/sh
# Establish the prescribed framework only on the ephemeral macOS CI runner.
set -eu
if [ "${GITHUB_ACTIONS:-}" != true ] || [ "${RUNNER_OS:-}" != macOS ]; then
    echo 'This installer is reserved for ephemeral macOS CI.' >&2
    exit 2
fi
: "${RUNNER_TEMP:?CI temporary directory is required}"
: "${GITHUB_PATH:?CI path file is required}"
scratch=$(mktemp -d "$RUNNER_TEMP/synthesis-python.XXXXXX")
package="$scratch/python.pkg"
signature="$scratch/signature.txt"
trap 'rm -f "$package" "$signature"; rmdir "$scratch"' EXIT HUP INT TERM
# Digest from the Python.org 3.12.3 macOS package Sigstore messageDigest.
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
    --output "$package" https://www.python.org/ftp/python/3.12.3/python-3.12.3-macos11.pkg
printf '%s  %s\n' 70a701542ff297760ac5e20f81d0e610aaaa1aba016e411788aa80029e571c5e "$package" | shasum -a 256 -c -
pkgutil --check-signature "$package" > "$signature"
grep -F 'Developer ID Installer: Python Software Foundation (BMM5U3QVKW)' "$signature" >/dev/null
sudo installer -pkg "$package" -target /
framework=/Library/Frameworks/Python.framework/Versions/3.12/bin
"$framework/python3" -I -B -c 'import sys; assert sys.version_info[:3] == (3, 12, 3), sys.version'
# The signed distribution supplies this TLS-root setup; never disable HTTPS verification.
"/Applications/Python 3.12/Install Certificates.command"
printf '%s\n' "$framework" >> "$GITHUB_PATH"
