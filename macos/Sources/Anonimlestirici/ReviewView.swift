import SwiftUI

// MARK: - E3 Önizleme ve onay

struct ReviewView: View {
    @ObservedObject var model: AnonymizeModel
    @EnvironmentObject var engine: EngineClient
    @State private var search = ""
    @State private var typeFilter = ""
    @State private var selection = Set<Int>()
    @State private var adding = false

    private var kinds: [EntityKind] { engine.hello?.types ?? [] }

    private var rows: [Candidate] {
        model.candidates.filter { c in
            (typeFilter.isEmpty || c.type == typeFilter)
                && (search.isEmpty || c.value.localizedCaseInsensitiveContains(search)
                    || c.code.localizedCaseInsensitiveContains(search))
        }
    }

    private var selected: Candidate? {
        guard let id = selection.first else { return nil }
        return model.candidates.first { $0.id == id }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title).font(.title3.weight(.semibold)).lineLimit(2)
            ForEach(model.warnings, id: \.self) { w in
                Label(w, systemImage: "exclamationmark.triangle").font(.callout).foregroundStyle(.orange)
            }
            HStack {
                TextField("Ara", text: $search).textFieldStyle(.roundedBorder).frame(maxWidth: 240)
                Picker("", selection: $typeFilter) {
                    Text("Tümü (\(model.candidates.count))").tag("")
                    ForEach(kinds) { k in
                        let n = model.candidates.filter { $0.type == k.value }.count
                        if n > 0 { Text("\(k.label) (\(n))").tag(k.value) }
                    }
                }
                .labelsHidden().frame(maxWidth: 200)
                Spacer()
                Button("+ Değer ekle") { adding = true }
            }
            HSplitView {
                table.frame(minWidth: 520)
                DetailPanel(candidate: selected, multiFile: model.documents.count > 1) { c in model.exclude(c) }
                    .frame(minWidth: 230, idealWidth: 280)
            }
            HStack {
                Text(summary).font(.callout).foregroundStyle(.secondary)
                Spacer()
                Button("Geri") { model.continueSameSession() }
                Button("Anonimleştir ve Kaydet") { model.save() }
                    .keyboardShortcut(.defaultAction)
                    .disabled(model.candidates.isEmpty)
            }
        }
        .padding(20)
        .sheet(isPresented: $adding) {
            AddValueSheet(kinds: kinds, preset: search) { value, type in
                Task {
                    let (id, count) = await model.addManual(value, type: type)
                    if let id { selection = [id] }
                    if count == 0 {
                        model.alert = AlertItem(title: "Bulunamadı",
                                                message: "\"\(value)\" dosyada geçmiyor. Yine de listeye eklendi.")
                    }
                }
            }
        }
        .onAppear { if selection.isEmpty, let f = model.candidates.first { selection = [f.id] } }
    }

    private var title: String {
        let occ = model.candidates.filter(\.accepted).map(\.count).reduce(0, +)
        return model.documents.joined(separator: ", ") + " · \(model.candidates.count) farklı değer, \(occ) geçiş"
    }

    private var summary: String {
        let skipped = model.candidates.filter { !$0.accepted }.count
        return skipped == 0
            ? "Bütün değerler anonimleştirilecek."
            : "\(skipped) değer atlanacak. Atlananlar eşleştirme tablosunun \"Atlananlar\" sayfasına yazılır."
    }

    private var table: some View {
        Table(rows, selection: $selection) {
            TableColumn("") { c in
                Toggle("", isOn: Binding(get: { c.accepted }, set: { model.setAccepted([c.id], $0) }))
                    .labelsHidden()
                    .toggleStyle(.checkbox)
            }
            .width(24)
            TableColumn("Tür") { c in
                Menu(c.typeLabel) {
                    ForEach(kinds) { k in
                        Button(k.label) { model.setType(c.id, k.value) }
                    }
                }
                .menuStyle(.borderlessButton)
                .fixedSize()
            }
            .width(min: 90, ideal: 120)
            TableColumn("Değer") { c in
                Text(c.value).foregroundStyle(c.accepted ? Color.primary : Color.secondary)
            }
            TableColumn("Kod") { c in
                Text(c.code.isEmpty ? "atlanacak" : c.code)
                    .font(.system(.body, design: .monospaced))
                    .foregroundStyle(c.code.isEmpty ? Color.secondary : Color.accentColor)
            }
            .width(min: 90, ideal: 120)
            TableColumn("Adet") { c in Text("\(c.count)").monospacedDigit() }.width(44)
            TableColumn("Yöntem") { c in
                HStack(spacing: 4) {
                    if c.lowConfidence {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundStyle(.yellow)
                            .help("Düşük güven: Bu değer kişisel veri olmayabilir (ör. hem ad hem sıradan kelime). Kontrol edip işaretleyin.")
                            .accessibilityLabel("Düşük güven")
                    }
                    Text(c.sources.joined(separator: ", ")).foregroundStyle(.secondary)
                }
            }
            .width(min: 170, ideal: 230)
        }
        .contextMenu(forSelectionType: Int.self) { ids in
            Button("İşaretle") { model.setAccepted(Array(ids), true) }
            Button("İşareti kaldır") { model.setAccepted(Array(ids), false) }
        }
    }
}

struct DetailPanel: View {
    let candidate: Candidate?
    let multiFile: Bool
    let exclude: (Candidate) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let c = candidate {
                ScrollView {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("GEÇTİĞİ YERLER").font(.caption).foregroundStyle(.secondary)
                        ForEach(Array(c.occurrences.enumerated()), id: \.offset) { _, o in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(multiFile ? "\(o.file) · \(o.location)" : o.location)
                                    .font(.caption).foregroundStyle(.secondary)
                                Text(highlighted(o)).textSelection(.enabled)
                            }
                        }
                        if c.count > c.occurrences.count {
                            Text("… ve \(c.count - c.occurrences.count) geçiş daha").foregroundStyle(.secondary)
                        }
                        if !c.variants.isEmpty {
                            Text("DİĞER YAZIMLAR").font(.caption).foregroundStyle(.secondary).padding(.top, 6)
                            Text(c.variants.joined(separator: ", "))
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(10)
                }
                Button("Asla listesine ekle") { exclude(c) }
                    .help("Bu değer bundan sonra hiçbir dosyada anonimleştirilmez.")
                    .padding([.horizontal, .bottom], 10)
            } else {
                Text("Bir satır seçin.").foregroundStyle(.secondary).padding()
                Spacer()
            }
        }
        .background(Color(nsColor: .textBackgroundColor))
    }

    private func highlighted(_ o: Occurrence) -> AttributedString {
        let ns = o.context as NSString
        let s = max(0, min(o.start, ns.length)), e = max(s, min(o.end, ns.length))
        var out = AttributedString(ns.substring(to: s))
        var mid = AttributedString(ns.substring(with: NSRange(location: s, length: e - s)))
        mid.backgroundColor = Color.yellow.opacity(0.45)
        mid.font = .body.bold()
        out += mid
        out += AttributedString(ns.substring(from: e))
        return out
    }
}

struct AddValueSheet: View {
    let kinds: [EntityKind]
    let preset: String
    let done: (String, String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var value = ""
    @State private var type = "ÖZEL"

    var body: some View {
        Form {
            TextField("Metin", text: $value, prompt: Text("ör. Hat-3, Proje Atlas, Gülşah"))
            Picker("Tür", selection: $type) {
                ForEach(kinds) { Text($0.label).tag($0.value) }
            }
            Text("Metin bütün dosyada aranır; büyük/küçük harf fark etmez.").font(.callout).foregroundStyle(.secondary)
            HStack {
                Spacer()
                Button("Vazgeç") { dismiss() }.keyboardShortcut(.cancelAction)
                Button("Ekle") {
                    done(value.trimmingCharacters(in: .whitespaces), type)
                    dismiss()
                }
                .keyboardShortcut(.defaultAction)
                .disabled(value.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
        .padding(20)
        .frame(width: 420)
        .onAppear { value = preset }
    }
}
