#!/usr/bin/env bash
set -Eeuo pipefail
case "$(uname -s)" in Darwin) os=macos ;; Linux) os=linux ;; *) os=unsupported ;; esac
case "$(uname -m)" in arm64|aarch64) arch=arm64 ;; x86_64|amd64) arch=x86_64 ;; *) arch="$(uname -m)" ;; esac
printf '%s-%s' "$os" "$arch"
