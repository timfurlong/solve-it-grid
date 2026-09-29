#!/usr/bin/env bash
# Build "Solve It Grid.app" from the Swift package and sign it.
# Usage: scripts/build-app.sh [--install]
#   --install  replace ~/Applications/Solve It Grid.app and launch it
set -euo pipefail
cd "$(dirname "$0")/.."

APP="build/Solve It Grid.app"
swift build -c release --product SolveItGrid

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp .build/release/SolveItGrid "$APP/Contents/MacOS/SolveItGrid"
cp Bundle/Info.plist "$APP/Contents/Info.plist"
cp Bundle/AppIcon.icns "$APP/Contents/Resources/AppIcon.icns"

# Prefer a local Apple Development identity (notifications behave best with a real signature);
# fall back to ad-hoc. The identity is read at build time and never stored in the repo.
IDENTITY=$(security find-identity -v -p codesigning 2>/dev/null | awk -F'"' '/Apple Development/ {print $2; exit}')
if [[ -n "$IDENTITY" ]]; then
    echo "Signing with an Apple Development identity"
    codesign --force --options runtime --sign "$IDENTITY" "$APP"
else
    echo "Signing ad-hoc"
    codesign --force --options runtime --sign - "$APP"
fi
codesign --verify --verbose "$APP"

if [[ "${1:-}" == "--install" ]]; then
    TARGET="$HOME/Applications/Solve It Grid.app"
    osascript -e 'tell application "Solve It Grid" to quit' >/dev/null 2>&1 || true
    mkdir -p "$HOME/Applications"
    rm -rf "$TARGET"
    cp -R "$APP" "$TARGET"
    # Refresh Launch Services so a new icon shows up in notifications and Finder.
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$TARGET" || true
    open "$TARGET"
    echo "Installed and launched $TARGET"
fi
