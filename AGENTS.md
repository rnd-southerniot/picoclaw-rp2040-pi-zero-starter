# AGENTS.md

## Global Working Agreements for This Repo

### Safety
- RP2040 is the final authority for motion safety.
- Do not bypass hardware safety checks in software.
- No autonomous movement during smoke tests unless explicitly requested.
- All command handlers must support a dry-run path.

### Architecture
- Keep Linux-side orchestration on Raspberry Pi Zero.
- Keep real-time control on RP2040.
- Start with JSON-lines over serial.
- Prefer modular Python files over large monoliths.

### Code style
- Small functions.
- Clear logging.
- Explicit config.
- Avoid hidden magic.

### Testing
- Add syntax-check and a dry-run smoke path.
- Avoid tests that require real hardware by default.
