#!/bin/bash
# Anonimleştirici.app'i derler, motoru ve dil modelini içine koyar, imzalar ve paketler.
#
#   ./packaging/build_mac.sh                      # yerel deneme: ad-hoc imzalı .app + .dmg
#   CHANNEL=direct ./packaging/build_mac.sh       # GitHub sürümü: Developer ID imzası + notarize + .dmg
#   CHANNEL=appstore ./packaging/build_mac.sh     # Mac App Store: sandbox, ağ izni yok, imzalı .pkg
#
# Ortam değişkenleri:
#   BUNDLE_ID            uygulama kimliği (Store'a gitmeden kesinleşmeli)
#   BUILD_NUMBER         CFBundleVersion; verilmezse git commit sayısı
#   SIGN_IDENTITY        uygulama imza kimliği ("-" = ad-hoc)
#                        direct:   "Developer ID Application: Ad Soyad (TEAMID)"
#                        appstore: "Apple Distribution: Ad Soyad (TEAMID)"
#   INSTALLER_IDENTITY   appstore için "3rd Party Mac Developer Installer: Ad Soyad (TEAMID)"
#   TEAM_ID              appstore için ekip kimliği
#   PROVISIONING_PROFILE appstore için indirilen .provisionprofile dosyası
#   NOTARY_PROFILE       direct için `xcrun notarytool store-credentials` ile kaydedilen profil adı
#   SKIP_ENGINE=1        motoru yeniden derleme (yalnızca Swift değiştiyse)
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY="${PYTHON:-.venv/bin/python}"
CHANNEL="${CHANNEL:-local}"
BUNDLE_ID="${BUNDLE_ID:-io.github.meparlak.anonimlestirici}"
VERSION=$("$PY" -c "import anonimlestirici; print(anonimlestirici.__version__)")
BUILD_NUMBER="${BUILD_NUMBER:-$(git rev-list --count HEAD 2>/dev/null || date +%Y%m%d%H%M)}"
SIGN_IDENTITY="${SIGN_IDENTITY:--}"
OUT="dist"
APP="$OUT/Anonimlestirici.app"
PKG_DIR="packaging/macos"

case "$CHANNEL" in
  appstore) ENTITLEMENTS="$PKG_DIR/App.entitlements"; SWIFT_FLAGS=(-D STORE_BUILD) ;;
  *)        ENTITLEMENTS="$PKG_DIR/App-DirectDownload.entitlements"; SWIFT_FLAGS=() ;;
esac
echo "→ Anonimleştirici $VERSION ($BUILD_NUMBER), kanal: $CHANNEL, kimlik: $BUNDLE_ID"

# --- 1. Dil modeli
if [ ! -f anonimlestirici/models/ner/model.onnx ]; then
  echo "→ Dil modeli indiriliyor"
  ./packaging/fetch_model.sh
fi

# --- 2. Motor (Python, PyInstaller)
if [ "${SKIP_ENGINE:-0}" != "1" ] || [ ! -d "$OUT/engine/AnonimEngine.app" ]; then
  echo "→ Motor paketleniyor"
  rm -rf build/engine "$OUT/engine"
  BUNDLE_ID="$BUNDLE_ID" "$PY" -m PyInstaller --noconfirm --clean --log-level WARN \
    --workpath build/engine --distpath "$OUT/engine" packaging/engine.spec
fi

# --- 3. Swift arayüzü
echo "→ Arayüz derleniyor"
SDK="${SDKROOT:-$(xcrun --show-sdk-path)}"
mkdir -p build/swift
# Bazı Command Line Tools 16 kurulumlarında SwiftBridging modülü iki kez tanımlı; sanal katmanla birini gizle.
OVERLAY_ARGS=()
CLT_MAP="/Library/Developer/CommandLineTools/usr/include/swift/module.modulemap"
if [ -f "$CLT_MAP" ] && [ -f "$(dirname "$CLT_MAP")/bridging.modulemap" ]; then
  : > build/swift/empty.modulemap
  cat > build/swift/overlay.yaml <<YAML
{ "version": 0, "case-sensitive": "false", "roots": [ { "type": "directory", "name": "$(dirname "$CLT_MAP")",
  "contents": [ { "type": "file", "name": "module.modulemap", "external-contents": "$ROOT/build/swift/empty.modulemap" } ] } ] }
YAML
  OVERLAY_ARGS=(-vfsoverlay build/swift/overlay.yaml -Xcc -ivfsoverlay -Xcc build/swift/overlay.yaml)
fi
swiftc -parse-as-library -O -whole-module-optimization -target arm64-apple-macos13.0 -sdk "$SDK" \
  ${OVERLAY_ARGS[@]+"${OVERLAY_ARGS[@]}"} ${SWIFT_FLAGS[@]+"${SWIFT_FLAGS[@]}"} \
  macos/Sources/Anonimlestirici/*.swift -o build/swift/Anonimlestirici

# --- 4. Uygulama paketi
echo "→ Uygulama paketi"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" "$APP/Contents/Helpers"
cp build/swift/Anonimlestirici "$APP/Contents/MacOS/Anonimlestirici"
sed -e "s/@BUNDLE_ID@/$BUNDLE_ID/" -e "s/@VERSION@/$VERSION/" -e "s/@BUILD@/$BUILD_NUMBER/" \
  "$PKG_DIR/Info.plist.in" > "$APP/Contents/Info.plist"
printf 'APPL????' > "$APP/Contents/PkgInfo"
cp packaging/Anonimlestirici.icns "$APP/Contents/Resources/AppIcon.icns"
cp "$PKG_DIR/PrivacyInfo.xcprivacy" "$APP/Contents/Resources/"
"$PY" packaging/collect_licenses.py "$APP/Contents/Resources/Licenses" >/dev/null
ditto "$OUT/engine/AnonimEngine.app" "$APP/Contents/Helpers/AnonimEngine.app"
if [ "$CHANNEL" = "appstore" ] && [ -n "${PROVISIONING_PROFILE:-}" ]; then
  cp "$PROVISIONING_PROFILE" "$APP/Contents/embedded.provisionprofile"
fi

# --- 5. İmza: içten dışa
echo "→ İmzalanıyor ($SIGN_IDENTITY)"
SIGN_ARGS=(--force --sign "$SIGN_IDENTITY")
if [ "$SIGN_IDENTITY" != "-" ]; then
  SIGN_ARGS+=(--timestamp)
  [ "$CHANNEL" = "direct" ] && SIGN_ARGS+=(--options runtime)
fi
APP_ENT="$ENTITLEMENTS"
if [ "$CHANNEL" = "appstore" ] && [ -n "${TEAM_ID:-}" ]; then
  APP_ENT="build/swift/App.entitlements"
  cp "$ENTITLEMENTS" "$APP_ENT"
  /usr/libexec/PlistBuddy -c "Add :com.apple.application-identifier string $TEAM_ID.$BUNDLE_ID" "$APP_ENT"
  /usr/libexec/PlistBuddy -c "Add :com.apple.developer.team-identifier string $TEAM_ID" "$APP_ENT"
fi
HELPER="$APP/Contents/Helpers/AnonimEngine.app"
# motorun içindeki bütün kütüphaneler (.so, .dylib, Python)
find "$HELPER" -type f \( -name "*.so" -o -name "*.dylib" -o -perm -u+x \) -print0 | while IFS= read -r -d '' f; do
  if file "$f" | grep -q "Mach-O"; then
    [ "$f" = "$HELPER/Contents/MacOS/anonim-engine" ] && continue
    codesign "${SIGN_ARGS[@]}" "$f" 2>/dev/null
  fi
done
find "$HELPER" -name "*.framework" -type d -prune -print0 | while IFS= read -r -d '' fw; do
  codesign "${SIGN_ARGS[@]}" "$fw"
done
codesign "${SIGN_ARGS[@]}" --entitlements "$PKG_DIR/Engine.entitlements" "$HELPER/Contents/MacOS/anonim-engine"
codesign "${SIGN_ARGS[@]}" --entitlements "$PKG_DIR/Engine.entitlements" "$HELPER"
codesign "${SIGN_ARGS[@]}" --entitlements "$APP_ENT" "$APP"
codesign --verify --deep --strict "$APP"
echo "   imza doğrulandı"

# --- 6. Paket
case "$CHANNEL" in
  appstore)
    : "${INSTALLER_IDENTITY:?App Store paketi için INSTALLER_IDENTITY gerekli}"
    PKG="$OUT/Anonimlestirici-$VERSION-$BUILD_NUMBER.pkg"
    productbuild --component "$APP" /Applications --sign "$INSTALLER_IDENTITY" "$PKG"
    echo "Hazır: $PKG  →  Transporter uygulamasıyla App Store Connect'e yükleyin."
    ;;
  *)
    DMG="$OUT/Anonimlestirici.dmg"  # sabit ad: "en son sürümü indir" bağlantısı her zaman çalışsın
    STAGE=$(mktemp -d)
    ditto "$APP" "$STAGE/Anonimlestirici.app"
    ln -s /Applications "$STAGE/Applications"
    rm -f "$DMG"
    hdiutil create -volname "Anonimleştirici" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
    rm -rf "$STAGE"
    if [ "$CHANNEL" = "direct" ] && [ "$SIGN_IDENTITY" != "-" ]; then
      codesign --force --timestamp --sign "$SIGN_IDENTITY" "$DMG"
      if [ -n "${NOTARY_PROFILE:-}" ]; then
        echo "→ Apple onayına (notarization) gönderiliyor"
        xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait
        xcrun stapler staple "$DMG"
      fi
    fi
    echo "Hazır: $DMG ($(du -h "$DMG" | cut -f1))"
    ;;
esac
