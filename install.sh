#!/bin/sh
# Installs the care-voice standalone executable from a GitHub Release.
#
#   curl -fsSL https://raw.githubusercontent.com/superintelligenceco/care-voice/main/install.sh | sh
#
# Environment variables:
#   CARE_VOICE_VERSION      Release tag to install, for example v0.2.0. Defaults to the latest release.
#   CARE_VOICE_INSTALL_DIR  Directory for the executable. Defaults to ~/.local/bin.
set -eu

repo="superintelligenceco/care-voice"
version="${CARE_VOICE_VERSION:-latest}"
install_dir="${CARE_VOICE_INSTALL_DIR:-$HOME/.local/bin}"

fail() {
  echo "care-voice install: $*" >&2
  exit 1
}

case "$(uname -s)" in
  Linux) os=linux ;;
  Darwin) os=macos ;;
  MINGW* | MSYS* | CYGWIN*) os=windows ;;
  *) fail "unsupported operating system: $(uname -s)" ;;
esac

case "$(uname -m)" in
  x86_64 | amd64) arch=x64 ;;
  aarch64 | arm64) arch=arm64 ;;
  *) fail "unsupported architecture: $(uname -m)" ;;
esac

asset="care-voice-$os-$arch"
name="care-voice"
if [ "$os" = windows ]; then
  [ "$arch" = x64 ] || fail "only x64 builds exist for Windows"
  asset="$asset.exe"
  name="care-voice.exe"
fi

if [ "$version" = latest ]; then
  base="https://github.com/$repo/releases/latest/download"
else
  case "$version" in v*) ;; *) version="v$version" ;; esac
  base="https://github.com/$repo/releases/download/$version"
fi

if command -v curl > /dev/null 2>&1; then
  fetch() { curl -fsSL -o "$2" "$1"; }
elif command -v wget > /dev/null 2>&1; then
  fetch() { wget -q -O "$2" "$1"; }
else
  fail "install curl or wget first"
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM

echo "Downloading $asset ($version)"
fetch "$base/$asset" "$tmp/$asset" || fail "could not download $base/$asset"
fetch "$base/SHA256SUMS" "$tmp/SHA256SUMS" || fail "could not download $base/SHA256SUMS"

expected="$(awk -v f="$asset" '$2 == f || $2 == "*" f { print $1 }' "$tmp/SHA256SUMS")"
[ -n "$expected" ] || fail "SHA256SUMS has no entry for $asset"
if command -v sha256sum > /dev/null 2>&1; then
  actual="$(sha256sum "$tmp/$asset" | awk '{ print $1 }')"
elif command -v shasum > /dev/null 2>&1; then
  actual="$(shasum -a 256 "$tmp/$asset" | awk '{ print $1 }')"
else
  fail "install sha256sum or shasum to verify the download"
fi
[ "$expected" = "$actual" ] || fail "checksum mismatch for $asset"

mkdir -p "$install_dir"
chmod +x "$tmp/$asset"
mv "$tmp/$asset" "$install_dir/$name"
echo "Installed $("$install_dir/$name" --version) to $install_dir/$name"

case ":$PATH:" in
  *":$install_dir:"*) ;;
  *) echo "Add $install_dir to your PATH to run care-voice from any directory." ;;
esac
