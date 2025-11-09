"""
Base Actor - Abstract base class for all actors
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pathlib import Path

from .utils import (
    ProxyManager,
    RateLimiter,
    DataExporter,
    CacheManager,
    retry_with_backoff
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class BaseActor(ABC):
    """
    Abstract base class for all scraping actors

    Provides common functionality:
        - Proxy management
        - Rate limiting
        - Caching
        - Data export
        - Error handling
    """

    def __init__(
        self,
        proxy_config: Optional[Dict[str, Any]] = None,
        rate_limit: Optional[Dict[str, int]] = None,
        cache_config: Optional[Dict[str, Any]] = None,
        output_dir: str = "output"
    ):
        """
        Initialize base actor

        Args:
            proxy_config: Proxy configuration dict
            rate_limit: Rate limit config (max_requests, time_window)
            cache_config: Cache configuration dict
            output_dir: Output directory for results
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize proxy manager
        self.proxy_manager = None
        if proxy_config and proxy_config.get('enabled', True):
            proxies = proxy_config.get('proxies', [])
            rotation_strategy = proxy_config.get('rotation_strategy', 'round_robin')

            if proxies:
                self.proxy_manager = ProxyManager(proxies, rotation_strategy)
                logger.info(f"Initialized proxy manager with {len(proxies)} proxies")

        # Initialize rate limiter
        self.rate_limiter = None
        if rate_limit:
            max_requests = rate_limit.get('max_requests', 30)
            time_window = rate_limit.get('time_window', 60)
            self.rate_limiter = RateLimiter(max_requests, time_window)
            logger.info(f"Initialized rate limiter: {max_requests} req/{time_window}s")

        # Initialize cache
        self.cache = None
        if cache_config and cache_config.get('enabled', True):
            cache_dir = cache_config.get('cache_dir', '.cache')
            ttl = cache_config.get('ttl', 86400)
            self.cache = CacheManager(cache_dir, ttl)
            logger.info(f"Initialized cache with TTL: {ttl}s")

        # Data exporter
        self.exporter = DataExporter()

        # Results storage
        self.results = []

    @abstractmethod
    async def scrape(self, input_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Main scraping method - must be implemented by subclass

        Args:
            input_data: Input parameters for scraping

        Returns:
            List of scraped data dictionaries
        """
        pass

    @abstractmethod
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """
        Validate input parameters - must be implemented by subclass

        Args:
            input_data: Input parameters to validate

        Returns:
            True if valid, raises ValueError if invalid
        """
        pass

    async def run(
        self,
        input_data: Dict[str, Any],
        export_formats: List[str] = ['json', 'csv']
    ) -> List[Dict[str, Any]]:
        """
        Run the actor with given input

        Args:
            input_data: Input parameters
            export_formats: List of export formats

        Returns:
            Scraped results
        """
        try:
            # Validate input
            logger.info("Validating input...")
            self.validate_input(input_data)

            # Run scraping
            logger.info("Starting scrape...")
            start_time = asyncio.get_event_loop().time()

            self.results = await self.scrape(input_data)

            end_time = asyncio.get_event_loop().time()
            duration = end_time - start_time

            logger.info(
                f"Scraping completed. "
                f"Results: {len(self.results)} items in {duration:.2f}s"
            )

            # Export results
            if self.results and export_formats:
                await self.export_results(export_formats)

            return self.results

        except Exception as e:
            logger.error(f"Error running actor: {e}", exc_info=True)
            raise

    async def export_results(
        self,
        formats: List[str] = ['json', 'csv'],
        filename: Optional[str] = None
    ) -> Dict[str, Path]:
        """
        Export results to specified formats

        Args:
            formats: List of formats to export
            filename: Base filename (default: actor name)

        Returns:
            Dict of format -> filepath
        """
        if not self.results:
            logger.warning("No results to export")
            return {}

        if filename is None:
            filename = self.__class__.__name__.lower()

        logger.info(f"Exporting {len(self.results)} results to {formats}")

        exported_files = self.exporter.auto_export(
            self.results,
            filename,
            formats,
            str(self.output_dir)
        )

        return exported_files

    async def get_proxy(self) -> Optional[str | Dict[str, str]]:
        """Get next proxy from proxy manager"""
        if self.proxy_manager:
            proxy = self.proxy_manager.get_proxy()
            logger.debug(f"Using proxy: {proxy}")
            return proxy
        return None

    async def rate_limit(self) -> None:
        """Apply rate limiting"""
        if self.rate_limiter:
            await self.rate_limiter.acquire()

    def get_from_cache(self, key: str) -> Optional[Any]:
        """Get data from cache"""
        if self.cache:
            return self.cache.get(key)
        return None

    def save_to_cache(self, key: str, data: Any) -> None:
        """Save data to cache"""
        if self.cache:
            self.cache.set(key, data)

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the actor run"""
        stats = {
            'total_results': len(self.results),
            'output_dir': str(self.output_dir)
        }

        if self.proxy_manager:
            stats['proxy_stats'] = self.proxy_manager.get_stats()

        if self.rate_limiter:
            stats['rate_limiter'] = {
                'current_usage': self.rate_limiter.current_usage,
                'available_requests': self.rate_limiter.available_requests
            }

        if self.cache:
            stats['cache_stats'] = self.cache.get_stats()

        return stats

    async def cleanup(self) -> None:
        """Cleanup resources (override if needed)"""
        logger.info("Cleaning up...")
