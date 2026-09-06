FROM ghcr.io/astral-sh/uv:0.12.6@sha256:88bc6eb1ccd4b82efd0e1b530caffabddf50dc2bf612e66c14ea25b8ee8a4d3d AS uv

FROM mcr.microsoft.com/devcontainers/python:3.14-bookworm@sha256:640278ebf1120722dc525430600787c0f92c93c792a98c7fc24994b1c9189aad

COPY --from=uv /uv /uvx /usr/local/bin/
