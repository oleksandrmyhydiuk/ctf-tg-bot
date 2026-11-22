# Sandbox image (ctf-sandbox). Built automatically by the bot on first start,
# or can be built manually: docker build -f sandbox.Dockerfile -t ctf-sandbox:3 .
# Ubuntu 22.04 and all packages are multi-arch (amd64 / arm64): builds natively for the host.
# If you modify this file, bump the IMAGE tag in config.py (ctf-sandbox:4 ...).
ARG BASE_IMAGE=ubuntu:22.04
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      sudo procps psmisc file tree curl iproute2 lsof netcat-openbsd sqlite3 \
      nginx apache2 postgresql postgresql-client \
      acl git binutils openssl cron iptables \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -u 1000 -M -d /home/student -s /bin/bash student \
 && echo 'student ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/student \
 && chmod 440 /etc/sudoers.d/student \
 && useradd -m -u 1001 -s /bin/bash attacker \
 && useradd -m -u 1002 -G www-data -s /bin/bash defender
