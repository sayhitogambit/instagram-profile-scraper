"""
Instagram Scraper - Input/Output Schemas
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class InstagramScraperInput(BaseModel):
    """Input schema for Instagram Scraper"""

    urls: Optional[List[str]] = Field(
        None,
        description="Instagram profile/post URLs"
    )

    username: Optional[str] = Field(
        None,
        description="Instagram username (without @)",
        example="nasa"
    )

    scrape_type: str = Field(
        "profile",
        description="Type: profile, posts, reels, hashtag, location"
    )

    max_posts: int = Field(
        30,
        ge=1,
        le=500,
        description="Maximum posts to scrape"
    )

    include_comments: bool = Field(
        False,
        description="Include comments for posts"
    )

    max_comments_per_post: int = Field(
        100,
        ge=0,
        le=500,
        description="Max comments per post"
    )

    date_from: Optional[str] = Field(
        None,
        description="Filter posts from date (YYYY-MM-DD)"
    )

    date_to: Optional[str] = Field(
        None,
        description="Filter posts to date (YYYY-MM-DD)"
    )

    login_session: Optional[Dict[str, str]] = Field(
        None,
        description="Login cookies for authenticated access"
    )

    @validator('scrape_type')
    def validate_scrape_type(cls, v):
        valid = ['profile', 'posts', 'reels', 'hashtag', 'location']
        if v not in valid:
            raise ValueError(f"scrape_type must be one of: {valid}")
        return v

    def model_post_init(self, __context):
        if not self.urls and not self.username:
            raise ValueError("Either 'urls' or 'username' must be provided")


class InstagramComment(BaseModel):
    """Instagram comment schema"""
    comment_id: str
    text: str
    author_username: str
    author_verified: bool = False
    timestamp: str
    likes: int = 0
    replies_count: int = 0


class InstagramPost(BaseModel):
    """Instagram post schema"""
    shortcode: str  # Post ID
    type: str  # image, video, carousel
    caption: str = ""
    hashtags: List[str] = []
    mentions: List[str] = []
    tagged_users: List[str] = []
    timestamp: str
    likes: int
    comments_count: int
    video_views: Optional[int] = None
    shares: int = 0  # 2025 metric
    media_urls: List[str] = []
    thumbnail_url: Optional[str] = None
    location: Optional[Dict[str, Any]] = None
    is_sponsored: bool = False
    comments: List[InstagramComment] = []


class InstagramProfile(BaseModel):
    """Instagram profile schema"""
    username: str
    full_name: str
    biography: str = ""
    external_url: Optional[str] = None
    follower_count: int
    following_count: int
    post_count: int
    is_verified: bool = False
    is_private: bool = False
    is_business: bool = False
    category: Optional[str] = None
    profile_pic_url: str
    profile_pic_url_hd: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "username": "nasa",
                "full_name": "NASA",
                "biography": "Exploring the universe",
                "follower_count": 80000000,
                "following_count": 70,
                "post_count": 4500,
                "is_verified": True,
                "is_private": False
            }
        }
