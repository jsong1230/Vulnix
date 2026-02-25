# Vulnix Security Extension Changelog

## [0.1.0] - 2026-02-26

### Added
- Real-time vulnerability detection via Vulnix server API
- Inline diagnostics with severity-based highlighting (Critical, High, Medium, Low)
- Code actions: apply AI-generated patches directly in the editor
- Vulnerability detail panel (webview) with full description and patch diff
- False positive pattern management with glob file filtering
- Auto-sync false positive rules from team server (every 5 minutes)
- Status bar indicator (connected / offline / analyzing)
- Korean / English UI support (`vscode.env.language` detection)
- Configurable severity filter (`all`, `high`, `critical`)
- 500ms debounce on file save to avoid excessive API calls

### Configuration
- `vulnix.serverUrl` — Vulnix API server URL
- `vulnix.apiKey` — API key for authentication
- `vulnix.analyzeOnSave` — Enable/disable analysis on file save
- `vulnix.severityFilter` — Minimum severity to display

### Commands
- `Vulnix: Analyze Current File`
- `Vulnix: Show Vulnerability Detail`
- `Vulnix: Sync False Positive Patterns`
- `Vulnix: Clear Diagnostics`
- `Vulnix: Apply Patch`
