# PicoClaw Integration Area

This folder is reserved for future PicoClaw-backed mission-agent integration.

It now includes a vendored reference snapshot:
- `siot-pico-bot-2/` copied from `rnd-southerniot/siot-pico-bot-2`
- local adjustments in the copied config:
  - IMU moved to `GP16/GP17`
  - left encoder remapped to `GP6/GP7` to avoid pin conflict

Current bridge execution (`robot-agent/`) does not depend on anything in this folder.
