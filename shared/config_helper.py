"""
Universal configuration helper for all actors
Supports IPRoyal residential proxies and manual proxy configuration
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()


def get_proxy_config(actor_name: str = '', default_country: str = 'us') -> Dict[str, Any]:
    """
    Get proxy configuration with IPRoyal support

    Priority:
    1. IPRoyal residential proxies (if configured)
    2. Manual PROXY_SERVER configuration
    3. No proxies (disabled)

    Args:
        actor_name: Name of the actor (for logging)
        default_country: Default country for IPRoyal targeting

    Returns:
        Proxy configuration dict
    """
    # Try IPRoyal first
    try:
        from shared.iproyal_config import IPRoyalConfig

        iproyal = IPRoyalConfig()
        if iproyal.is_configured():
            print(f"✓ Using IPRoyal residential proxies for {actor_name}")
            return iproyal.get_proxy_config_for_actor(
                country=default_country,
                rotation_strategy=os.getenv('PROXY_ROTATION', 'smart')
            )
    except Exception as e:
        print(f"⚠️  IPRoyal config error: {e}")

    # Fall back to manual proxy configuration
    proxy_enabled = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
    if not proxy_enabled:
        print(f"ℹ️  Proxies disabled for {actor_name}")
        return {'enabled': False, 'proxies': []}

    proxies = []
    proxy_server = os.getenv('PROXY_SERVER')

    if proxy_server:
        proxy_config = {'server': proxy_server}

        username = os.getenv('PROXY_USERNAME')
        password = os.getenv('PROXY_PASSWORD')

        if username and password:
            proxy_config['username'] = username
            proxy_config['password'] = password

        proxies.append(proxy_config)
        print(f"✓ Using manual proxy configuration for {actor_name}")

    return {
        'enabled': bool(proxies),
        'proxies': proxies,
        'rotation_strategy': os.getenv('PROXY_ROTATION', 'round_robin')
    }


def get_rate_limit_config(default_requests: int = 30, default_window: int = 60) -> Dict[str, int]:
    """Get rate limiting configuration"""
    return {
        'max_requests': int(os.getenv('RATE_LIMIT_REQUESTS', str(default_requests))),
        'time_window': int(os.getenv('RATE_LIMIT_WINDOW', str(default_window)))
    }


def get_cache_config(actor_name: str) -> Dict[str, Any]:
    """Get caching configuration"""
    return {
        'enabled': os.getenv('CACHE_ENABLED', 'true').lower() == 'true',
        'cache_dir': os.getenv('CACHE_DIR', f'.cache/{actor_name}'),
        'ttl': int(os.getenv('CACHE_TTL', '3600'))
    }


def load_actor_config(
    actor_name: str,
    default_country: str = 'us',
    default_rate_limit: int = 30,
    default_rate_window: int = 60
) -> Dict[str, Any]:
    """
    Load complete configuration for an actor

    Args:
        actor_name: Actor name (e.g., 'reddit', 'amazon')
        default_country: Default country for IPRoyal proxies
        default_rate_limit: Default max requests
        default_rate_window: Default time window in seconds

    Returns:
        Complete configuration dict
    """
    return {
        'proxy': get_proxy_config(actor_name, default_country),
        'rate_limit': get_rate_limit_config(default_rate_limit, default_rate_window),
        'cache': get_cache_config(actor_name),
        'output_dir': os.getenv('OUTPUT_DIR', f'output/{actor_name}'),
        'log_level': os.getenv('LOG_LEVEL', 'INFO')
    }
