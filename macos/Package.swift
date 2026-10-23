// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "Anonimlestirici",
    defaultLocalization: "tr",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "Anonimlestirici",
            path: "Sources/Anonimlestirici"
        ),
    ]
)
