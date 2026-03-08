# First boot checklist for Raspberry Pi Zero on the same LAN

## 1) Flash OS
Use Raspberry Pi OS Lite.

## 2) During imaging
Preconfigure:
- hostname: `pi-zero`
- username: `arif`
- Wi-Fi SSID/password for your current LAN
- enable SSH

## 3) After power-up
From your laptop on the same network, try:

```bash
./host-tools/find-pi-zero.sh
./host-tools/ssh-pi-zero.sh arif
```

If mDNS does not resolve, use the router DHCP lease table or run the host tools in `host-tools/`.

## 4) On the Pi
Upload or clone this project and run:

```bash
cd /path/to/picoclaw-rp2040-pi-zero-starter
./pi-zero/bootstrap_pi_zero.sh
```

This deploys into `/opt/picoclaw-rp2040` and enables `robot-agent.service`.

## 5) Connect RP2040 over Wi-Fi
Ensure RP2040 and Pi Zero are on the same network, then set the RP2040 TCP endpoint in:

```bash
robot-agent/config.yaml
```

Default endpoint is `rp2040.local:8765`.
