from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


def is_url_allowed(url: str, allow_private: bool = False) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return False

    if allow_private:
        return True

    if host in {"localhost"}:
        return False

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False

    for info in infos:
        ip = info[4][0]
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_multicast
            or addr.is_reserved
        ):
            return False
    return True
