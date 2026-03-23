#!/bin/bash
# =============================================================================
# Build the Dyno-IP .deb package
# Run on a Debian/Ubuntu system (or WSL)
#
# Usage:  ./build-deb.sh [version]
# Output: dynoip_1.0.0_all.deb
# =============================================================================

set -euo pipefail

VERSION="${1:-1.0.0}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build/dynoip_${VERSION}_all"

echo "Building dynoip ${VERSION}..."

# Clean previous build
rm -rf "${SCRIPT_DIR}/build"
mkdir -p "${BUILD_DIR}"

# ── Copy package structure ──
cp -r "${SCRIPT_DIR}/deb-root/DEBIAN" "${BUILD_DIR}/DEBIAN"
cp -r "${SCRIPT_DIR}/deb-root/etc" "${BUILD_DIR}/etc"
cp -r "${SCRIPT_DIR}/deb-root/lib" "${BUILD_DIR}/lib"

# ── Install binary ──
mkdir -p "${BUILD_DIR}/usr/bin"
cp "${SCRIPT_DIR}/dynoip-update" "${BUILD_DIR}/usr/bin/dynoip-update"
chmod 755 "${BUILD_DIR}/usr/bin/dynoip-update"

# ── Install core library ──
mkdir -p "${BUILD_DIR}/usr/lib/dynoip"
cp "${SCRIPT_DIR}/../dynoip_core.py" "${BUILD_DIR}/usr/lib/dynoip/dynoip_core.py"

# Add a symlink so the binary can find dynoip_core
# (the binary adds its own dir to sys.path; we put core alongside it)
# Actually, better: copy core next to the binary
cp "${SCRIPT_DIR}/../dynoip_core.py" "${BUILD_DIR}/usr/bin/dynoip_core.py"

# ── Set version in control file ──
sed -i "s/^Version:.*/Version: ${VERSION}/" "${BUILD_DIR}/DEBIAN/control"

# ── Fix permissions ──
chmod 755 "${BUILD_DIR}/DEBIAN/postinst"
chmod 755 "${BUILD_DIR}/DEBIAN/prerm"
chmod 755 "${BUILD_DIR}/DEBIAN/postrm"
chmod 644 "${BUILD_DIR}/DEBIAN/control"
chmod 644 "${BUILD_DIR}/DEBIAN/conffiles"
chmod 644 "${BUILD_DIR}/etc/dynoip/config"
chmod 644 "${BUILD_DIR}/lib/systemd/system/dynoip.service"
chmod 644 "${BUILD_DIR}/lib/systemd/system/dynoip.timer"

# ── Build .deb ──
dpkg-deb --build "${BUILD_DIR}"

# Move to output
mv "${SCRIPT_DIR}/build/dynoip_${VERSION}_all.deb" "${SCRIPT_DIR}/dynoip_${VERSION}_all.deb"

echo ""
echo "✓ Built: ${SCRIPT_DIR}/dynoip_${VERSION}_all.deb"
echo ""
echo "Install: sudo dpkg -i dynoip_${VERSION}_all.deb"
echo "         sudo apt-get install -f  # fix dependencies if needed"

# Cleanup
rm -rf "${SCRIPT_DIR}/build"
