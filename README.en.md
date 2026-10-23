# Anonimleştirici

[Türkçe](README.md) | English

I wanted to give my Excel, Word and PowerPoint files to an AI assistant for analysis and root cause work, but they were full of names, Turkish ID numbers (TC kimlik no), phone numbers, addresses, department and organization names. Cleaning them by hand is slow and easy to get wrong, so I wrote this small macOS app to do it for me.

You give it a file and it gives you two files back:

1. An anonymized copy in the same format and layout, with personal data replaced by codes such as `[KİŞİ_1]` (person), `[TELEFON_2]` (phone) or `[BİRİM_1]` (department). This is the file you share with the AI.
2. A mapping table (Excel) that tells you which code stands for which real value. This one stays with you.

When the AI answers, the "Geri Çevir" (reverse) tab turns the codes in its reply back into the real names using the mapping table.

Everything runs on your own Mac. The app never connects to the internet.

## What it detects

Person names (Turkish first-name dictionary, titles such as Sayın, Dr., Bey, Hanım, and Excel column headers), TC ID numbers (with checksum), Turkish phone numbers, e-mail addresses, street addresses, department and organization names (by Turkish suffixes such as Müdürlüğü, Başkanlığı, Üniversitesi, A.Ş.), IBANs, and optionally licence plates, dates and your own list of terms.

The same person always gets the same code, across the whole file and across files processed together. Before anything is written, all findings are shown in a review table where you can untick false positives or add values that were missed.

The interface is in Turkish, since the detection rules are built for Turkish documents.

## Supported files

.xlsx, .xlsm, .csv, .docx, .pptx, .txt, .md. In Office files only the text changes; images, charts, styles, formulas and pivot tables are copied as they are. Document metadata (author, last modified by, comment authors, tracked-change authors) is cleaned too.

## Install

No coding or terminal needed.

1. [**Download Anonimleştirici**](https://github.com/meparlak/anonimlestirici/releases/latest/download/Anonimlestirici.dmg) (about 580 MB).
2. Open `Anonimlestirici.dmg` and drag the app into the Applications folder.
3. The first time you open it, macOS shows a security warning because the app is not yet signed with a paid Apple Developer ID. This does not mean anything is wrong with the app; Apple simply has not reviewed it. Go to System Settings → Privacy & Security and click **Open Anyway** once.

Requires a Mac with Apple silicon (M1 or later) and macOS 13 or later. A step-by-step guide with screenshots is available in Turkish: [docs/KURULUM.md](docs/KURULUM.md), [docs/KULLANIM.md](docs/KULLANIM.md).

## Privacy: your data never leaves your Mac

- Files are processed only on your Mac. The app does not connect to any server and sends no data.
- No account, no cloud, no analytics, ads, usage statistics or crash reports.
- The Turkish language model ships inside the app and runs locally; nothing is downloaded at runtime.
- The app runs in the macOS sandbox and can only access files you choose or drop onto it. Temporary copies stay inside the sandbox and are deleted afterwards.
- The only exception is the experimental, off-by-default "Local LLM" option, which sends text only to a model server you specify (by default Ollama on the same Mac) and asks for confirmation before using any other address. The Mac App Store version has neither this option nor network access.

To verify: turn off Wi-Fi and use the app, or watch it with a network monitor such as LuLu or Little Snitch. The only file in the source code that opens a network connection is [`llm.py`](anonimlestirici/core/detectors/llm.py).

## Things to keep in mind

- No automatic tool catches everything. Structured data (ID, phone, e-mail, IBAN) is caught very reliably; names depend on a dictionary and context. That is why the review step exists. Have a quick look at the output before sharing it.
- With very few people, indirect details (department + title + date) can still identify someone.
- Under GDPR/KVKK, data is pseudonymized, not anonymous, as long as the mapping table exists.
- Text inside images is not processed.

## How it works

The interface is SwiftUI. It runs a bundled, sandboxed Python engine (`Contents/Helpers/AnonimEngine.app`) that parses Office files with lxml and combines rules, a Turkish name dictionary, column headers and a bundled Turkish NER model ([ModernBERT-TR PII](https://huggingface.co/ytu-ce-cosmos/modernbert-tr-pii-ner) by YTU COSMOS, Apache-2.0) running on the CPU with ONNX Runtime. No network access is needed.

## Build from source

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev,ner]"
./packaging/fetch_model.sh      # NER model, ~600 MB
.venv/bin/python -m pytest
./packaging/build_mac.sh        # dist/Anonimlestirici.app and .dmg
```

## License

The source code is available under the [PolyForm Noncommercial License 1.0.0](LICENSE). Individuals, schools, universities, public bodies and charities may use, study and modify it free of charge for noncommercial purposes. Any commercial use, including use inside a company and selling the app or a modified version, requires my permission: enesparlakq@gmail.com. Bundled third-party components keep their own licenses, see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
