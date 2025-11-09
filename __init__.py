"""
Instagram Scraper Actor

Extract profile data, posts, reels, stories, comments, and engagement metrics
from Instagram profiles, hashtags, and locations.
"""

from .scraper import InstagramScraper
from .schema import (
    InstagramScraperInput,
    InstagramProfile,
    InstagramPost,
    InstagramComment
)

__all__ = [
    'InstagramScraper',
    'InstagramScraperInput',
    'InstagramProfile',
    'InstagramPost',
    'InstagramComment'
]
