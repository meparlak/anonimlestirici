#!/bin/bash
# Türkçe KVKK NER modelini (ytu-ce-cosmos/modernbert-tr-pii-ner, Apache-2.0) sabit bir sürümden indirir.
#   VARIANT=full|quantized ./packaging/fetch_model.sh
# Model git'e eklenmez; derleme sırasında uygulamanın içine konur.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="ytu-ce-cosmos/modernbert-tr-pii-ner"
REV="69b2563bf18126fc3285ac2c66371b483bb6d7ec"
VARIANT="${VARIANT:-full}"
DEST="anonimlestirici/models/ner"
mkdir -p "$DEST"
base="https://huggingface.co/$REPO/resolve/$REV"
fetch() { curl -fL --retry 5 -C - -o "$2" "$base/$1"; }
fetch config.json "$DEST/config.json"
fetch tokenizer.json "$DEST/tokenizer.json"
fetch README.md "$DEST/README.md"
if [ "$VARIANT" = "quantized" ]; then
  fetch onnx/model_quantized.onnx "$DEST/model.onnx"
else
  fetch onnx/model.onnx "$DEST/model.onnx"
fi
cat > "$DEST/KAYNAK.txt" <<TXT
Model: https://huggingface.co/$REPO (sürüm $REV, $VARIANT)
Lisans: Apache-2.0
Geliştiren: YTU COSMOS (Yıldız Teknik Üniversitesi)
TXT
shasum -a 256 "$DEST/model.onnx"
