"""Instagram Scraper - Configuration with IPRoyal Support"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.config_helper import load_actor_config

def load_config():
    """Load Instagram scraper configuration with IPRoyal proxies"""
    return load_actor_config(
        actor_name='instagram',
        default_country='us',
        default_rate_limit=40,  # 40 per hour = conservative
        default_rate_window=3600  # 1 hour window
    )
