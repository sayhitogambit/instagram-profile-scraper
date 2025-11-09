"""
IPRoyal Residential Proxy Configuration Helper
Automatically configures proxies from environment variables
"""

import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()


class IPRoyalConfig:
    """IPRoyal residential proxy configuration"""

    def __init__(self):
        self.username = os.getenv('IPROYAL_USERNAME')
        self.password = os.getenv('IPROYAL_PASSWORD')
        self.host = os.getenv('IPROYAL_HOST', 'geo.iproyal.com')
        self.port = int(os.getenv('IPROYAL_PORT', '12321'))
        self.protocol = os.getenv('IPROYAL_PROTOCOL', 'http')
        self.api_key = os.getenv('IPROYAL_API_KEY')

    def is_configured(self) -> bool:
        """Check if IPRoyal credentials are configured"""
        return bool(self.username and self.password)

    def get_proxy_url(self, country: Optional[str] = None, state: Optional[str] = None,
                      city: Optional[str] = None, session: Optional[str] = None) -> str:
        """
        Generate IPRoyal proxy URL with optional targeting

        Args:
            country: Country code (e.g., 'us', 'gb', 'de')
            state: State/region (e.g., 'california', 'texas')
            city: City name (e.g., 'los-angeles', 'new-york')
            session: Session ID for sticky sessions

        Returns:
            Formatted proxy URL
        """
        if not self.is_configured():
            raise ValueError("IPRoyal credentials not configured. Check .env file.")

        # Build password with targeting parameters
        password = self.password

        # Only add targeting if password doesn't already have it
        has_targeting = '_country-' in password or '_state-' in password or '_city-' in password

        if not has_targeting:
            if country:
                password += f"_country-{country.lower()}"
            if state:
                password += f"_state-{state.lower().replace(' ', '-')}"
            if city:
                password += f"_city-{city.lower().replace(' ', '-')}"

        if session:
            password += f"_session-{session}"

        # Format: protocol://username:password@host:port
        return f"{self.protocol}://{self.username}:{password}@{self.host}:{self.port}"

    def get_proxy_dict(self, **kwargs) -> Dict[str, str]:
        """
        Get proxy dictionary for requests library

        Args:
            **kwargs: Targeting parameters (country, state, city, session)

        Returns:
            Dict with 'http' and 'https' proxy URLs
        """
        proxy_url = self.get_proxy_url(**kwargs)
        return {
            'http': proxy_url,
            'https': proxy_url
        }

    def get_proxy_config_for_actor(self, country: str = 'us',
                                   rotation_strategy: str = 'smart') -> Dict:
        """
        Get proxy configuration dict for BaseActor

        Args:
            country: Default country for targeting
            rotation_strategy: Proxy rotation strategy

        Returns:
            Proxy config dict for actors
        """
        if not self.is_configured():
            print("⚠️  WARNING: IPRoyal not configured. Most actors will fail without proxies!")
            return {'enabled': False, 'proxies': []}

        # Create multiple proxy entries with different sessions for rotation
        proxies = []
        for i in range(5):  # 5 different sessions for rotation
            proxy_config = {
                'server': self.get_proxy_url(country=country, session=f"session{i}"),
                'username': self.username,
                'password': self.password
            }
            proxies.append(proxy_config)

        return {
            'enabled': True,
            'proxies': proxies,
            'rotation_strategy': rotation_strategy
        }

    def test_connection(self) -> bool:
        """Test IPRoyal proxy connection"""
        if not self.is_configured():
            print("❌ IPRoyal credentials not configured")
            return False

        try:
            import requests
            proxy_dict = self.get_proxy_dict(country='us')

            print(f"Testing IPRoyal connection...")
            print(f"  Host: {self.host}:{self.port}")
            print(f"  Username: {self.username}")
            print(f"  Protocol: {self.protocol}")

            response = requests.get(
                'https://ipv4.icanhazip.com',
                proxies=proxy_dict,
                timeout=10
            )

            if response.status_code == 200:
                ip = response.text.strip()
                print(f"✓ Connected successfully!")
                print(f"  Your IP: {ip}")
                return True
            else:
                print(f"❌ Connection failed: HTTP {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False


def load_iproyal_config() -> Optional[Dict]:
    """
    Quick helper to load IPRoyal config for actors
    Returns None if not configured
    """
    config = IPRoyalConfig()
    if config.is_configured():
        return config.get_proxy_config_for_actor()
    return None


# Example usage
if __name__ == "__main__":
    config = IPRoyalConfig()

    if config.is_configured():
        print("✓ IPRoyal Configuration Found")
        print(f"  Username: {config.username}")
        print(f"  Host: {config.host}:{config.port}")
        print()

        # Test connection
        config.test_connection()

        print()
        print("Example proxy URLs:")
        print(f"  US: {config.get_proxy_url(country='us')}")
        print(f"  UK: {config.get_proxy_url(country='gb')}")
        print(f"  US California: {config.get_proxy_url(country='us', state='california')}")

    else:
        print("❌ IPRoyal not configured")
        print("   Set IPROYAL_USERNAME and IPROYAL_PASSWORD in .env file")
