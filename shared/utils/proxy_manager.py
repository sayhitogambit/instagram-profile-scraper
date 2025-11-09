"""
Proxy Manager - Handles proxy rotation and health tracking
"""

import random
from typing import Optional, Dict, List
from dataclasses import dataclass, field


@dataclass
class ProxyStats:
    """Track proxy performance statistics"""
    success: int = 0
    failure: int = 0

    @property
    def success_rate(self) -> float:
        total = self.success + self.failure
        return self.success / total if total > 0 else 1.0

    @property
    def total_requests(self) -> int:
        return self.success + self.failure


class ProxyManager:
    """
    Manages proxy rotation with different strategies and health tracking

    Strategies:
        - round_robin: Cycle through proxies in order
        - random: Pick random proxy each time
        - smart: Use proxy with highest success rate
    """

    def __init__(
        self,
        proxies: List[str] | List[Dict[str, str]],
        rotation_strategy: str = "round_robin"
    ):
        """
        Initialize ProxyManager

        Args:
            proxies: List of proxy strings or dicts with server/username/password
            rotation_strategy: "round_robin", "random", or "smart"
        """
        self.proxies = proxies
        self.rotation_strategy = rotation_strategy
        self.current_index = 0
        self.proxy_stats: Dict[str, ProxyStats] = {}

        # Initialize stats for all proxies
        for proxy in self.proxies:
            proxy_key = self._get_proxy_key(proxy)
            self.proxy_stats[proxy_key] = ProxyStats()

    def _get_proxy_key(self, proxy: str | Dict[str, str]) -> str:
        """Get unique key for proxy"""
        if isinstance(proxy, dict):
            return proxy.get('server', str(proxy))
        return str(proxy)

    def get_proxy(self) -> str | Dict[str, str] | None:
        """
        Get next proxy based on rotation strategy

        Returns:
            Proxy string or dict, or None if no proxies available
        """
        if not self.proxies:
            return None

        if self.rotation_strategy == "round_robin":
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
            return proxy

        elif self.rotation_strategy == "random":
            return random.choice(self.proxies)

        elif self.rotation_strategy == "smart":
            # Filter out proxies with very low success rate
            viable_proxies = []
            for proxy in self.proxies:
                key = self._get_proxy_key(proxy)
                stats = self.proxy_stats[key]

                # Only consider if success rate > 10% or has less than 10 total requests
                if stats.success_rate > 0.1 or stats.total_requests < 10:
                    viable_proxies.append((proxy, stats.success_rate))

            if not viable_proxies:
                # All proxies have low success rate, reset and try again
                for stats in self.proxy_stats.values():
                    stats.success = 0
                    stats.failure = 0
                return random.choice(self.proxies)

            # Sort by success rate and pick best one
            viable_proxies.sort(key=lambda x: x[1], reverse=True)
            return viable_proxies[0][0]

        return None

    def report_success(self, proxy: str | Dict[str, str]) -> None:
        """Report successful request with this proxy"""
        key = self._get_proxy_key(proxy)
        if key in self.proxy_stats:
            self.proxy_stats[key].success += 1

    def report_failure(self, proxy: str | Dict[str, str]) -> None:
        """Report failed request with this proxy"""
        key = self._get_proxy_key(proxy)
        if key in self.proxy_stats:
            self.proxy_stats[key].failure += 1

    def get_stats(self) -> Dict[str, Dict[str, any]]:
        """Get statistics for all proxies"""
        return {
            key: {
                "success": stats.success,
                "failure": stats.failure,
                "success_rate": stats.success_rate,
                "total_requests": stats.total_requests
            }
            for key, stats in self.proxy_stats.items()
        }

    def remove_proxy(self, proxy: str | Dict[str, str]) -> None:
        """Remove a proxy from the pool (e.g., if permanently broken)"""
        if proxy in self.proxies:
            self.proxies.remove(proxy)
            key = self._get_proxy_key(proxy)
            if key in self.proxy_stats:
                del self.proxy_stats[key]

    def add_proxy(self, proxy: str | Dict[str, str]) -> None:
        """Add a new proxy to the pool"""
        self.proxies.append(proxy)
        key = self._get_proxy_key(proxy)
        self.proxy_stats[key] = ProxyStats()

    @property
    def total_proxies(self) -> int:
        """Get total number of proxies"""
        return len(self.proxies)

    @property
    def healthy_proxies(self) -> int:
        """Get number of proxies with success rate > 50%"""
        return sum(
            1 for stats in self.proxy_stats.values()
            if stats.success_rate > 0.5 and stats.total_requests > 5
        )
