"""
Cache Manager - Cache scraped data to reduce duplicate requests
"""

import json
import hashlib
import logging
from typing import Any, Optional
from pathlib import Path
import time

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Simple file-based cache manager (can be replaced with Redis)

    Example:
        cache = CacheManager(ttl=3600)  # 1 hour cache

        key = cache.make_key("https://example.com", {"param": "value"})
        cached = cache.get(key)

        if cached:
            return cached

        data = scrape_function()
        cache.set(key, data)
    """

    def __init__(
        self,
        cache_dir: str = ".cache",
        ttl: int = 86400,  # 24 hours default
        enabled: bool = True
    ):
        """
        Initialize CacheManager

        Args:
            cache_dir: Directory to store cache files
            ttl: Time to live in seconds (0 = never expire)
            enabled: Enable/disable caching
        """
        self.cache_dir = Path(cache_dir)
        self.ttl = ttl
        self.enabled = enabled

        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def make_key(self, *args, **kwargs) -> str:
        """
        Generate cache key from arguments

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            MD5 hash of serialized arguments
        """
        # Combine all arguments into a string
        key_parts = [str(arg) for arg in args]
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key_string = ":".join(key_parts)

        # Generate MD5 hash
        return hashlib.md5(key_string.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if not self.enabled:
            return None

        cache_file = self.cache_dir / f"{key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Check if expired
            if self.ttl > 0:
                cached_time = cache_data.get('timestamp', 0)
                current_time = time.time()

                if current_time - cached_time > self.ttl:
                    logger.debug(f"Cache expired for key: {key}")
                    cache_file.unlink()  # Delete expired cache
                    return None

            logger.debug(f"Cache hit for key: {key}")
            return cache_data.get('data')

        except Exception as e:
            logger.error(f"Error reading cache: {e}")
            return None

    def set(self, key: str, value: Any) -> None:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
        """
        if not self.enabled:
            return

        cache_file = self.cache_dir / f"{key}.json"

        try:
            cache_data = {
                'timestamp': time.time(),
                'data': value
            }

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, default=str)

            logger.debug(f"Cache set for key: {key}")

        except Exception as e:
            logger.error(f"Error writing cache: {e}")

    def delete(self, key: str) -> None:
        """Delete cache entry"""
        if not self.enabled:
            return

        cache_file = self.cache_dir / f"{key}.json"

        if cache_file.exists():
            cache_file.unlink()
            logger.debug(f"Cache deleted for key: {key}")

    def clear(self) -> None:
        """Clear all cache"""
        if not self.enabled:
            return

        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()

        logger.info("All cache cleared")

    def get_stats(self) -> dict:
        """Get cache statistics"""
        if not self.enabled:
            return {'enabled': False}

        cache_files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in cache_files)

        return {
            'enabled': True,
            'total_entries': len(cache_files),
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'cache_dir': str(self.cache_dir),
            'ttl': self.ttl
        }


class RedisCacheManager:
    """
    Redis-based cache manager for distributed caching

    Example:
        cache = RedisCacheManager(redis_url='redis://localhost:6379', ttl=3600)
        cache.set('key', {'data': 'value'})
        data = cache.get('key')
    """

    def __init__(
        self,
        redis_url: str = 'redis://localhost:6379',
        ttl: int = 86400,
        enabled: bool = True
    ):
        """
        Initialize RedisCacheManager

        Args:
            redis_url: Redis connection URL
            ttl: Time to live in seconds
            enabled: Enable/disable caching
        """
        self.redis_url = redis_url
        self.ttl = ttl
        self.enabled = enabled
        self.redis = None

        if self.enabled:
            try:
                import redis
                self.redis = redis.from_url(redis_url, decode_responses=False)
                self.redis.ping()  # Test connection
                logger.info(f"Connected to Redis: {redis_url}")

            except ImportError:
                logger.error("redis package not installed. Install with: pip install redis")
                self.enabled = False

            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self.enabled = False

    def make_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments"""
        key_parts = [str(arg) for arg in args]
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key_string = ":".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache"""
        if not self.enabled or not self.redis:
            return None

        try:
            data = self.redis.get(key)
            if data:
                logger.debug(f"Redis cache hit for key: {key}")
                return json.loads(data)
            return None

        except Exception as e:
            logger.error(f"Error reading from Redis: {e}")
            return None

    def set(self, key: str, value: Any) -> None:
        """Set value in Redis cache"""
        if not self.enabled or not self.redis:
            return

        try:
            serialized = json.dumps(value, default=str)

            if self.ttl > 0:
                self.redis.setex(key, self.ttl, serialized)
            else:
                self.redis.set(key, serialized)

            logger.debug(f"Redis cache set for key: {key}")

        except Exception as e:
            logger.error(f"Error writing to Redis: {e}")

    def delete(self, key: str) -> None:
        """Delete from Redis cache"""
        if not self.enabled or not self.redis:
            return

        try:
            self.redis.delete(key)
            logger.debug(f"Redis cache deleted for key: {key}")

        except Exception as e:
            logger.error(f"Error deleting from Redis: {e}")

    def clear(self) -> None:
        """Clear all Redis cache"""
        if not self.enabled or not self.redis:
            return

        try:
            self.redis.flushdb()
            logger.info("All Redis cache cleared")

        except Exception as e:
            logger.error(f"Error clearing Redis: {e}")

    def get_stats(self) -> dict:
        """Get Redis cache statistics"""
        if not self.enabled or not self.redis:
            return {'enabled': False}

        try:
            info = self.redis.info()
            return {
                'enabled': True,
                'total_keys': self.redis.dbsize(),
                'used_memory_mb': round(info.get('used_memory', 0) / (1024 * 1024), 2),
                'ttl': self.ttl
            }

        except Exception as e:
            logger.error(f"Error getting Redis stats: {e}")
            return {'enabled': True, 'error': str(e)}
