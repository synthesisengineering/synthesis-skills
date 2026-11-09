# The knowledge-base connector, for Google Cloud Run or any container host. Build from the root of the
# synthesis-skills repository, since the image takes the plugin's YAML reader from synthesis/:
#
#   docker build --platform linux/amd64 -f skills/synthesis-kb-distribution/scripts/connector/Dockerfile \
#     -t kb-connector .
#
# Dockerfile.dockerignore beside this file limits the build context to the files copied below.
FROM python:3.12.16-slim-trixie@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# git and ssh fetch the published repository with the deploy key.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git openssh-client ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Every package pinned and hash-checked; --no-deps so nothing outside the lock is installed.
COPY skills/synthesis-kb-distribution/scripts/connector/requirements.txt /tmp/requirements.txt
RUN pip install --require-hashes --no-deps -r /tmp/requirements.txt && rm /tmp/requirements.txt

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin app
WORKDIR /app
COPY synthesis/__init__.py synthesis/yamlish.py /app/synthesis/
COPY skills/synthesis-kb-distribution/scripts/connector/kb_connector/ /app/kb_connector/

USER 10001
ENV HOME=/home/app \
    KB_WORK_DIR=/tmp/kb-connector \
    PORT=8080
EXPOSE 8080
CMD ["python", "-m", "kb_connector"]
