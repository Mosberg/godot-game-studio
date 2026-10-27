---
name: export-and-release
description: Export Godot games for Windows, Linux, macOS, Web and Android and publish to itch.io or Steam - presets, templates, signing, versions, size, and common failures. Includes .NET-specific limits for Godot 4.7.x.
---

# Export & release

1. Match **export templates** to the editor version exactly (4.7.2.stable). Editor > Manage Export Templates (or headless download is not scripted here).
2. `godot_create_export_presets` then `godot_export(preset, output)`. Check `godot_list_export_presets` for names.
3. **Windows**: embed PCK, set icon (`.ico`), product/company metadata; code signing optional. **Linux**: `x86_64`, `.sh` launcher optional. **macOS**: universal binary, notarisation needed for distribution outside Steam. **Web**: Compatibility renderer, serve with correct MIME and (for threads) COOP/COEP headers. **Android**: JDK 17, Android SDK, debug/release keystore, gradle build for custom permissions.
4. **.NET**: needs the .NET SDK on the build machine; web export unsupported; Android/iOS experimental; end user machines need nothing extra for desktop exports. .NET 8/9 reach end of support on 10 Nov 2026; Godot 4.8 will require .NET 10.
5. itch.io: `butler push build user/game:windows`. Steam: Steamworks SDK + GodotSteam (not the Steam-distributed editor for C#).
6. Checklist: version string, debug off, `.gitignore` clean, test the *exported* binary, record sizes, crash logs path (`user://logs`), AI-content disclosure for stores that require it.
