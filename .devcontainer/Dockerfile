FROM ghcr.io/astral-sh/uv:0.12.6@sha256:88bc6eb1ccd4b82efd0e1b530caffabddf50dc2bf612e66c14ea25b8ee8a4d3d AS uv

# bolt, which runs the gate's jigs, built from a pinned commit. It takes wrench
# by path from a checkout beside it, so both are cloned as siblings. bolt
# publishes no Cargo.lock, so its crates.io dependencies resolve at build time.
FROM rust:1.97-bookworm AS bolt
ARG BOLT_REV=e7ed512ce3e160128570bec7776bca4881b6a4ce
ARG WRENCH_REV=be2e4de16ad449a2dcd974834626175f2318890f
WORKDIR /src
RUN git clone https://github.com/scriptedworld/bolt \
 && git -C bolt checkout --quiet ${BOLT_REV} \
 && git clone https://github.com/scriptedworld/wrench \
 && git -C wrench checkout --quiet ${WRENCH_REV} \
 && cargo build --release --manifest-path bolt/Cargo.toml \
 && install -D bolt/target/release/bolt /opt/bolt/bin/bolt

FROM ghcr.io/gitleaks/gitleaks:v8.30.1 AS gitleaks

FROM mcr.microsoft.com/devcontainers/python:3.14-bookworm@sha256:640278ebf1120722dc525430600787c0f92c93c792a98c7fc24994b1c9189aad

COPY --from=uv /uv /uvx /usr/local/bin/
COPY --from=bolt /opt/bolt/bin/bolt /usr/local/bin/bolt
COPY --from=gitleaks /usr/bin/gitleaks /usr/local/bin/gitleaks

# The jigs call these from PATH. Versions match uv.lock, so the container, the
# lockfile and `uv run` agree; mypy and the suite run through `uv run` instead.
# Their directory leads PATH, ahead of the base image's own pylint and bandit.
ENV UV_TOOL_DIR=/opt/uv-tools UV_TOOL_BIN_DIR=/opt/uv-tools/bin
ENV PATH=/opt/uv-tools/bin:${PATH}
RUN uv tool install ruff==0.16.4 \
 && uv tool install pylint==4.0.7 \
 && uv tool install complexipy==7.0.1 \
 && uv tool install vulture==2.16 \
 && uv tool install interrogate==1.7.0 \
 && uv tool install bandit==1.9.4 \
 && uv tool install detect-secrets==1.5.0 \
 && uv tool install rust-just==1.58.0

# The gate reads toolbox's jigs from a checkout beside the workspace.
ARG TOOLBOX_REV=438c6704b356eacbaef741dbe40c7e127f33f84c
RUN git clone https://github.com/scriptedworld/toolbox /workspaces/toolbox \
 && git -C /workspaces/toolbox checkout --quiet ${TOOLBOX_REV} \
 && chown -R vscode:vscode /workspaces/toolbox
