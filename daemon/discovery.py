"""mDNS zero-configuration discovery broadcaster using zeroconf."""

import logging
import socket
from typing import Optional

from zeroconf import IPVersion, ServiceInfo, Zeroconf

from .config import CONFIG

logger = logging.getLogger("antigravity.discovery")


class DiscoveryService:
    def __init__(self):
        self._zeroconf: Optional[Zeroconf] = None
        self._service_info: Optional[ServiceInfo] = None

    def start(self):
        try:
            self._zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
            local_ip = CONFIG.local_ip
            ip_bytes = socket.inet_aton(local_ip)

            desc = {
                "version": CONFIG.version,
                "type": "antigravity-mobile-gateway",
                "port": str(CONFIG.port),
            }

            service_name = f"{CONFIG.mdns_service_name}.{CONFIG.mdns_service_type}"

            self._service_info = ServiceInfo(
                type_=CONFIG.mdns_service_type,
                name=service_name,
                addresses=[ip_bytes],
                port=CONFIG.port,
                properties=desc,
                server=f"{socket.gethostname().lower()}.local.",
            )

            self._zeroconf.register_service(self._service_info)
            logger.info("mDNS announcement active: %s on %s:%d", service_name, local_ip, CONFIG.port)
        except Exception as e:
            logger.warning("mDNS service registration warning (non-fatal): %s", e)

    def stop(self):
        if self._zeroconf and self._service_info:
            try:
                self._zeroconf.unregister_service(self._service_info)
                self._zeroconf.close()
                logger.info("mDNS discovery unregistered")
            except Exception as e:
                logger.warning("Error during mDNS shutdown: %s", e)
            finally:
                self._zeroconf = None
                self._service_info = None


DISCOVERY = DiscoveryService()
