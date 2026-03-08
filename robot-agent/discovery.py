from __future__ import annotations

import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, List, Optional


def _is_valid_host(host: str) -> bool:
    return bool(host and host.strip())


def _probe_host(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            return True
    except Exception:
        return False


def _local_ipv4() -> Optional[str]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:
        return None
    finally:
        sock.close()


def _subnet_hosts(prefix_or_ip: str) -> Iterable[str]:
    try:
        if "/" in prefix_or_ip:
            net = ipaddress.ip_network(prefix_or_ip, strict=False)
            for ip in net.hosts():
                yield str(ip)
            return
    except Exception:
        pass

    if prefix_or_ip.count(".") == 2:
        prefix = prefix_or_ip
    else:
        parts = prefix_or_ip.split(".")
        if len(parts) != 4:
            return
        prefix = ".".join(parts[:3])

    for i in range(2, 255):
        yield f"{prefix}.{i}"


def discover_tcp_host(
    configured_host: str,
    port: int,
    connect_timeout: float,
    enabled: bool,
    candidates: Optional[List[str]],
    subnet_scan: bool,
    subnet_prefix: Optional[str],
    cache_file: Optional[str],
    max_workers: int = 48,
):
    host = (configured_host or "").strip()
    if host and host.lower() != "auto":
        return host

    if not enabled:
        raise RuntimeError("TCP host is set to auto but discovery is disabled")

    candidate_hosts: List[str] = []

    if cache_file:
        try:
            cached = Path(cache_file).read_text(encoding="utf-8").strip()
            if _is_valid_host(cached):
                candidate_hosts.append(cached)
        except Exception:
            pass

    for item in candidates or []:
        if _is_valid_host(item):
            candidate_hosts.append(item.strip())

    seen = set()
    dedup_candidates = []
    for item in candidate_hosts:
        if item not in seen:
            dedup_candidates.append(item)
            seen.add(item)

    for candidate in dedup_candidates:
        if _probe_host(candidate, port=port, timeout=connect_timeout):
            if cache_file:
                Path(cache_file).parent.mkdir(parents=True, exist_ok=True)
                Path(cache_file).write_text(candidate + "\n", encoding="utf-8")
            return candidate

    if not subnet_scan:
        raise RuntimeError("Unable to discover RP2040 TCP host from candidates")

    local_ip = _local_ipv4()
    subnet_seed = subnet_prefix or local_ip
    if not subnet_seed:
        raise RuntimeError("Unable to discover local subnet for TCP scan")

    hosts = list(_subnet_hosts(subnet_seed))
    if local_ip in hosts:
        hosts.remove(local_ip)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {
            pool.submit(_probe_host, h, port, connect_timeout): h
            for h in hosts
        }
        for fut in as_completed(future_map):
            if fut.result():
                found = future_map[fut]
                if cache_file:
                    Path(cache_file).parent.mkdir(parents=True, exist_ok=True)
                    Path(cache_file).write_text(found + "\n", encoding="utf-8")
                return found

    raise RuntimeError("Unable to discover RP2040 TCP host on subnet scan")
