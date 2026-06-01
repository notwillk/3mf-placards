ARG BASE_IMAGE=mcr.microsoft.com/devcontainers/base:ubuntu-24.04
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    fontconfig \
    fonts-inter \
    fonts-lato \
    fonts-noto-mono \
    fonts-roboto-unhinted \
    git \
    jq \
    openscad \
    python3 \
    python3-yaml \
    shellcheck \
    shfmt \
  && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
  && apt-get update \
  && apt-get install -y --no-install-recommends nodejs \
  && npm install -g @moonrepo/cli@1 \
  && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://raw.githubusercontent.com/notwillk/checksy/main/scripts/install.sh | bash

RUN curl -fsSL https://astral.sh/uv/install.sh -o /tmp/uv-install.sh \
  && env UV_INSTALL_DIR=/usr/local/bin sh /tmp/uv-install.sh \
  && rm -f /tmp/uv-install.sh
