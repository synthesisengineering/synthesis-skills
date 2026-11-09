#!/bin/sh
# Build an organization's knowledge-base plugin and push it to the published repository.
#
#   publish_plugin.sh --config FILE --source DIR [--commit SHA]
#
# Runs build_plugin.py (beside this script) into a private temporary folder, clones the published
# repository, replaces everything in it but .git with the build, and pushes one commit made as a
# bot identity. When the build matches what is already published it pushes nothing and exits 0.
# Nobody else writes to the published repository: each run overwrites it.
#
# Environment (nothing defaults to any organization's repository or host):
#   KB_PUBLISH_REPO          the published repository's git URL (required)
#   KB_PUBLISH_BRANCH        the branch to publish (default: main)
#   KB_PUBLISH_KNOWN_HOSTS   the git host's known_hosts line(s), checked against the host's published
#                            fingerprints; required for an SSH URL, and the only host keys the push trusts
#   KB_PUBLISH_SSH_KEY_FILE  a private key for the push (optional; otherwise ssh's agent or config)
#   KB_PUBLISH_BOT_NAME      the commit author (default: kb-publish[bot])
#   KB_PUBLISH_BOT_EMAIL     its address (default: kb-publish@users.noreply.invalid)
#   PYTHON                   the interpreter for the build (default: python3)
#
# Prints the build's report, then `Published <plugin> <version> to <repository> (<branch>).` or
# `The published copy already matches this build; nothing to push.` Exit 1 on any failure, 2 on a
# usage error. A credential embedded in an https URL is never printed.
set -eu

usage() {
  echo "usage: publish_plugin.sh --config FILE --source DIR [--commit SHA]" >&2
  exit 2
}
die() {
  echo "publish_plugin: $*" >&2
  exit 1
}
redact() {
  sed 's#//[^/@]*@#//#g'
}

HERE=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
CONFIG='' SOURCE='' COMMIT=''
while [ $# -gt 0 ]; do
  case $1 in
    --config) [ $# -ge 2 ] || usage; CONFIG=$2; shift 2 ;;
    --source) [ $# -ge 2 ] || usage; SOURCE=$2; shift 2 ;;
    --commit) [ $# -ge 2 ] || usage; COMMIT=$2; shift 2 ;;
    *) usage ;;
  esac
done
[ -n "$CONFIG" ] && [ -n "$SOURCE" ] || usage

REPO=${KB_PUBLISH_REPO:-}
BRANCH=${KB_PUBLISH_BRANCH:-main}
[ -n "$REPO" ] || die "KB_PUBLISH_REPO is not set: give the published repository's git URL"
git check-ref-format --branch "$BRANCH" >/dev/null 2>&1 || die "KB_PUBLISH_BRANCH '$BRANCH' is not a branch name"
SHOWN=$(printf '%s\n' "$REPO" | redact)
case $REPO in
  ssh://* | git+ssh://* | ssh+git://*) SSH=yes ;;
  *://*) SSH=no ;;
  *) case ${REPO%%/*} in *:*) SSH=yes ;; *) SSH=no ;; esac ;;  # host:path is SSH; a local path is not
esac
if [ "$SSH" = yes ] && [ -z "${KB_PUBLISH_KNOWN_HOSTS:-}" ]; then
  die "KB_PUBLISH_KNOWN_HOSTS is not set: an SSH push needs the host's key, checked against its published fingerprints"
fi
KEY=${KB_PUBLISH_SSH_KEY_FILE:-}
if [ -n "$KEY" ]; then
  [ -r "$KEY" ] || die "KB_PUBLISH_SSH_KEY_FILE $KEY cannot be read"
  case $KEY in *"'"*) die "KB_PUBLISH_SSH_KEY_FILE must not contain a single quote" ;; esac
fi
COMMIT=$(git -C "$SOURCE" rev-parse --verify "${COMMIT:-HEAD}^{commit}") || die "no commit ${COMMIT:-HEAD} in $SOURCE"

TMP=${TMPDIR:-/tmp}
WORK=$(mktemp -d "${TMP%/}/kb-publish.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
trap 'exit 1' HUP INT TERM

"${PYTHON:-python3}" "$HERE/build_plugin.py" --config "$CONFIG" --source "$SOURCE" --out "$WORK/plugin" --commit "$COMMIT"

if [ "$SSH" = yes ]; then
  # Only the pinned keys are trusted: no user or system known_hosts, and an unknown key is refused.
  case $WORK in *"'"*) die "the temporary folder $WORK has a single quote in its path" ;; esac
  printf '%s\n' "$KB_PUBLISH_KNOWN_HOSTS" >"$WORK/known_hosts"
  GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh} -o UserKnownHostsFile='$WORK/known_hosts' -o GlobalKnownHostsFile=/dev/null"
  GIT_SSH_COMMAND="$GIT_SSH_COMMAND -o StrictHostKeyChecking=yes"
  [ -z "$KEY" ] || GIT_SSH_COMMAND="$GIT_SSH_COMMAND -i '$KEY' -o IdentitiesOnly=yes"
  export GIT_SSH_COMMAND
fi
GIT_TERMINAL_PROMPT=0
export GIT_TERMINAL_PROMPT

# 0: the branch exists; 2: reachable, but no such branch yet (a new repository or branch); else unreachable.
status=0
git ls-remote --exit-code --heads "$REPO" "refs/heads/$BRANCH" >/dev/null 2>"$WORK/reach" || status=$?
case $status in
  0) git clone --quiet --depth 1 --branch "$BRANCH" "$REPO" "$WORK/publish" 2>"$WORK/reach" ||
       { redact <"$WORK/reach" >&2; die "cannot clone $SHOWN ($BRANCH)"; } ;;
  2) git -c init.defaultBranch="$BRANCH" init --quiet "$WORK/publish" && git -C "$WORK/publish" remote add origin "$REPO" ;;
  *) redact <"$WORK/reach" >&2
     die "cannot reach $SHOWN: check the URL, that the deploy key may write to it, and KB_PUBLISH_KNOWN_HOSTS" ;;
esac

find "$WORK/publish" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp -R "$WORK/plugin/." "$WORK/publish/"
git -C "$WORK/publish" add -A
if git -C "$WORK/publish" diff --cached --quiet; then
  echo "The published copy already matches this build; nothing to push."
  exit 0
fi
LABEL=$("${PYTHON:-python3}" -c 'import json, sys; p = json.load(open(sys.argv[1]))["plugins"][0]
print(p["name"], p["version"])' "$WORK/plugin/.claude-plugin/marketplace.json")
git -C "$WORK/publish" -c user.name="${KB_PUBLISH_BOT_NAME:-kb-publish[bot]}" \
  -c user.email="${KB_PUBLISH_BOT_EMAIL:-kb-publish@users.noreply.invalid}" \
  commit --quiet -m "Publish $LABEL from $(printf '%.7s' "$COMMIT")"
git -C "$WORK/publish" push --quiet origin "HEAD:refs/heads/$BRANCH" 2>"$WORK/reach" ||
  { redact <"$WORK/reach" >&2; die "the push to $SHOWN ($BRANCH) was refused"; }
echo "Published $LABEL to $SHOWN ($BRANCH)."
