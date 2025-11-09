"""
Instagram Scraper
Extract profiles, posts, reels, and engagement metrics from Instagram
"""

import asyncio
import logging
import re
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scrapling import StealthyFetcher, DynamicFetcher
from shared.base_actor import BaseActor
from shared.utils import retry_with_backoff
from schema import (
    InstagramScraperInput,
    InstagramProfile,
    InstagramPost,
    InstagramComment
)

logger = logging.getLogger(__name__)


class InstagramScraper(BaseActor):
    """
    Instagram Scraper

    Features:
        - Extract profile data and statistics
        - Scrape posts, reels, stories
        - GraphQL API approach + browser fallback
        - Engagement metrics (likes, comments, shares)
        - Support hashtags and locations
        - REQUIRES residential proxies + login session
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base_url = "https://www.instagram.com"

    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input using Pydantic schema"""
        try:
            InstagramScraperInput(**input_data)
            return True
        except Exception as e:
            raise ValueError(f"Invalid input: {e}")

    async def scrape(self, input_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Main scraping method"""
        config = InstagramScraperInput(**input_data)

        logger.info(f"Starting Instagram scrape: {config.scrape_type}")

        # Determine username
        username = config.username
        if config.urls and not username:
            # Extract username from URL
            username = self._extract_username_from_url(config.urls[0])

        results = []

        if config.scrape_type == 'profile':
            # Scrape profile info
            profile = await self._scrape_profile(username, config.login_session)
            results = [profile.model_dump()]

        elif config.scrape_type in ['posts', 'reels']:
            # Scrape posts
            posts = await self._scrape_posts(
                username,
                config.max_posts,
                config.login_session
            )

            if config.include_comments:
                posts = await self._scrape_comments_batch(
                    posts,
                    config.max_comments_per_post
                )

            results = [post.model_dump() for post in posts]

        logger.info(f"Scraped {len(results)} items from Instagram")

        return results

    def _extract_username_from_url(self, url: str) -> str:
        """Extract username from Instagram URL"""
        match = re.search(r'instagram\.com/([^/\?]+)', url)
        if match:
            return match.group(1)
        return url

    @retry_with_backoff(max_retries=3, base_delay=3.0)
    async def _scrape_profile(
        self,
        username: str,
        login_session: Optional[Dict[str, str]] = None
    ) -> InstagramProfile:
        """
        Scrape Instagram profile using GraphQL API

        Instagram GraphQL endpoint: /api/v1/users/web_profile_info/
        """
        await self.rate_limit()

        url = f"{self.base_url}/api/v1/users/web_profile_info/?username={username}"

        headers = {
            'x-ig-app-id': '936619743392459',  # Instagram web app ID
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }

        # Add session cookies if provided
        if login_session:
            headers['Cookie'] = '; '.join([f"{k}={v}" for k, v in login_session.items()])

        proxy = await self.get_proxy()

        # IMPORTANT: Instagram REQUIRES residential proxies with session persistence
        if not proxy:
            logger.warning("No proxy configured - Instagram WILL block requests!")

        # StealthyFetcher is synchronous, not async
            try:
                fetcher = StealthyFetcher(proxy=proxy, headers=headers)
                response = fetcher.get(url)

                if response.status == 429:
                    raise Exception("Rate limited by Instagram - need to wait")

                if response.status == 401:
                    raise Exception("Unauthorized - login session required")

                data = json.loads(response.text)

                user_data = data.get('data', {}).get('user', {})

                profile = InstagramProfile(
                    username=user_data.get('username', username),
                    full_name=user_data.get('full_name', ''),
                    biography=user_data.get('biography', ''),
                    external_url=user_data.get('external_url'),
                    follower_count=user_data.get('edge_followed_by', {}).get('count', 0),
                    following_count=user_data.get('edge_follow', {}).get('count', 0),
                    post_count=user_data.get('edge_owner_to_timeline_media', {}).get('count', 0),
                    is_verified=user_data.get('is_verified', False),
                    is_private=user_data.get('is_private', False),
                    is_business=user_data.get('is_business_account', False),
                    category=user_data.get('category_name'),
                    profile_pic_url=user_data.get('profile_pic_url', ''),
                    profile_pic_url_hd=user_data.get('profile_pic_url_hd')
                )

                if proxy and self.proxy_manager:
                    self.proxy_manager.report_success(proxy)

                return profile

            except Exception as e:
                if proxy and self.proxy_manager:
                    self.proxy_manager.report_failure(proxy)
                raise

    async def _scrape_posts(
        self,
        username: str,
        max_posts: int,
        login_session: Optional[Dict[str, str]] = None
    ) -> List[InstagramPost]:
        """
        Scrape posts from Instagram profile

        Uses GraphQL API when possible, browser automation as fallback
        """
        posts = []

        # Try GraphQL approach first
        try:
            posts = await self._scrape_posts_graphql(username, max_posts, login_session)
        except Exception as e:
            logger.warning(f"GraphQL approach failed: {e}")
            logger.info("Falling back to browser automation...")

            # Fallback to browser automation
            try:
                posts = await self._scrape_posts_browser(username, max_posts, login_session)
            except Exception as e2:
                logger.error(f"Browser automation also failed: {e2}")

        return posts

    async def _scrape_posts_graphql(
        self,
        username: str,
        max_posts: int,
        login_session: Optional[Dict[str, str]] = None
    ) -> List[InstagramPost]:
        """Scrape posts using GraphQL API"""
        await self.rate_limit()

        # Instagram GraphQL endpoint for user media
        url = f"{self.base_url}/{username}/?__a=1&__d=dis"

        headers = {
            'x-ig-app-id': '936619743392459',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }

        if login_session:
            headers['Cookie'] = '; '.join([f"{k}={v}" for k, v in login_session.items()])

        proxy = await self.get_proxy()
        posts = []

        # StealthyFetcher is synchronous, not async
            try:
                fetcher = StealthyFetcher(proxy=proxy, headers=headers)
                response = fetcher.get(url)

                if response.status != 200:
                    raise Exception(f"Failed to fetch profile data: {response.status}")

                data = json.loads(response.text)

                # Extract user data
                user_data = data.get('graphql', {}).get('user', {}) or \
                           data.get('data', {}).get('user', {})

                if not user_data:
                    logger.warning("Could not extract user data from response")
                    return posts

                # Get media edges
                media_edges = user_data.get('edge_owner_to_timeline_media', {}).get('edges', [])

                logger.info(f"Found {len(media_edges)} posts in GraphQL response")

                for edge in media_edges[:max_posts]:
                    try:
                        node = edge.get('node', {})
                        post = self._parse_post_from_graphql(node, username)
                        if post:
                            posts.append(post)
                    except Exception as e:
                        logger.debug(f"Error parsing post: {e}")
                        continue

                # If we need more posts, paginate using end cursor
                if len(posts) < max_posts:
                    page_info = user_data.get('edge_owner_to_timeline_media', {}).get('page_info', {})
                    if page_info.get('has_next_page'):
                        end_cursor = page_info.get('end_cursor')
                        more_posts = await self._fetch_paginated_posts(
                            user_data.get('id'),
                            end_cursor,
                            max_posts - len(posts),
                            login_session
                        )
                        posts.extend(more_posts)

                if proxy and self.proxy_manager:
                    self.proxy_manager.report_success(proxy)

                logger.info(f"Successfully scraped {len(posts)} posts via GraphQL")

            except Exception as e:
                if proxy and self.proxy_manager:
                    self.proxy_manager.report_failure(proxy)
                raise

        return posts

    async def _fetch_paginated_posts(
        self,
        user_id: str,
        end_cursor: str,
        max_posts: int,
        login_session: Optional[Dict[str, str]] = None
    ) -> List[InstagramPost]:
        """Fetch paginated posts using GraphQL"""
        await self.rate_limit()

        # GraphQL query hash for user media (changes periodically)
        query_hash = "69cba40317214236af40e7efa697781d"  # May need updating

        variables = {
            "id": user_id,
            "first": min(max_posts, 50),
            "after": end_cursor
        }

        url = f"{self.base_url}/graphql/query/?query_hash={query_hash}&variables={json.dumps(variables)}"

        headers = {
            'x-ig-app-id': '936619743392459',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }

        if login_session:
            headers['Cookie'] = '; '.join([f"{k}={v}" for k, v in login_session.items()])

        proxy = await self.get_proxy()
        posts = []

        # StealthyFetcher is synchronous, not async
            try:
                fetcher = StealthyFetcher(proxy=proxy, headers=headers)
                response = fetcher.get(url)
                data = json.loads(response.text)

                edges = data.get('data', {}).get('user', {}).get('edge_owner_to_timeline_media', {}).get('edges', [])

                for edge in edges:
                    try:
                        node = edge.get('node', {})
                        post = self._parse_post_from_graphql(node, '')
                        if post:
                            posts.append(post)
                    except Exception as e:
                        logger.debug(f"Error parsing paginated post: {e}")
                        continue

            except Exception as e:
                logger.warning(f"Pagination failed: {e}")

        return posts

    def _parse_post_from_graphql(self, node: Dict[str, Any], username: str) -> Optional[InstagramPost]:
        """Parse post from GraphQL node data"""
        try:
            shortcode = node.get('shortcode', '')
            if not shortcode:
                return None

            # Extract caption
            caption = ''
            caption_edges = node.get('edge_media_to_caption', {}).get('edges', [])
            if caption_edges:
                caption = caption_edges[0].get('node', {}).get('text', '')

            # Extract media type
            typename = node.get('__typename', '')
            media_type = 'image'
            if typename == 'GraphVideo':
                media_type = 'video'
            elif typename == 'GraphSidecar':
                media_type = 'carousel'

            # Extract media URLs
            media_urls = []
            if media_type == 'carousel':
                sidecar_edges = node.get('edge_sidecar_to_children', {}).get('edges', [])
                for edge in sidecar_edges:
                    child_node = edge.get('node', {})
                    media_url = child_node.get('display_url') or child_node.get('video_url', '')
                    if media_url:
                        media_urls.append(media_url)
            else:
                media_url = node.get('display_url') or node.get('video_url', '')
                if media_url:
                    media_urls.append(media_url)

            # Extract engagement metrics
            likes = node.get('edge_media_preview_like', {}).get('count') or \
                   node.get('edge_liked_by', {}).get('count', 0)
            comments_count = node.get('edge_media_to_comment', {}).get('count', 0)

            # Create post object
            post = InstagramPost(
                shortcode=shortcode,
                post_url=f"{self.base_url}/p/{shortcode}/",
                media_type=media_type,
                media_urls=media_urls,
                caption=caption,
                likes=likes,
                comments_count=comments_count,
                timestamp=datetime.fromtimestamp(node.get('taken_at_timestamp', 0)),
                is_video=node.get('is_video', False),
                video_views=node.get('video_view_count', 0) if node.get('is_video') else 0,
                owner_username=node.get('owner', {}).get('username', username)
            )

            return post

        except Exception as e:
            logger.debug(f"Error parsing post from GraphQL: {e}")
            return None

    async def _scrape_posts_browser(
        self,
        username: str,
        max_posts: int,
        login_session: Optional[Dict[str, str]] = None
    ) -> List[InstagramPost]:
        """
        Scrape posts using browser automation (fallback)

        Uses Playwright through DynamicFetcher
        """
        posts = []
        proxy = await self.get_proxy()

        async with DynamicFetcher(
            proxy=proxy,
            headless=True,
            browser_type='chromium'
        ) as fetcher:
            try:
                await fetcher.goto(f"{self.base_url}/{username}/")

                # Wait for posts to load
                await fetcher.wait_for_selector('article', timeout=10000)

                # Scroll to load more posts
                scrolls_needed = (max_posts // 12) + 1  # Instagram loads ~12 posts at a time
                for i in range(scrolls_needed):
                    await fetcher.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    await asyncio.sleep(2)  # Human-like delay

                # Extract post links from the page
                page = fetcher.get_page()
                post_link_elements = page.css('article a[href*="/p/"]').getall()

                # Extract shortcodes from links
                shortcodes = []
                for link_html in post_link_elements:
                    match = re.search(r'/p/([^/\?]+)', link_html)
                    if match:
                        shortcode = match.group(1)
                        if shortcode not in shortcodes:
                            shortcodes.append(shortcode)

                logger.info(f"Found {len(shortcodes)} unique posts")

                # Visit each post to extract detailed data
                for shortcode in shortcodes[:max_posts]:
                    try:
                        await self.rate_limit()  # Respect rate limits
                        post_url = f"{self.base_url}/p/{shortcode}/"

                        await fetcher.goto(post_url)
                        await asyncio.sleep(2)  # Wait for load

                        # Extract page HTML
                        page = fetcher.get_page()
                        page_html = page.text if hasattr(page, 'text') else str(page)

                        # Try to extract data from embedded JSON
                        json_match = re.search(r'window\._sharedData\s*=\s*({.*?});', page_html, re.DOTALL)
                        if json_match:
                            try:
                                shared_data = json.loads(json_match.group(1))
                                post_data = shared_data.get('entry_data', {}).get('PostPage', [{}])[0]
                                post_media = post_data.get('graphql', {}).get('shortcode_media', {})

                                if post_media:
                                    post = self._parse_post_from_graphql(post_media, username)
                                    if post:
                                        posts.append(post)
                                        continue

                            except Exception as e:
                                logger.debug(f"Could not extract from shared data: {e}")

                        # Fallback: Parse from HTML
                        post = self._parse_post_from_browser_html(page_html, shortcode, username)
                        if post:
                            posts.append(post)

                    except Exception as e:
                        logger.warning(f"Error extracting post {shortcode}: {e}")
                        continue

                logger.info(f"Successfully scraped {len(posts)} posts via browser")

            except Exception as e:
                logger.error(f"Browser scraping failed: {e}")

        return posts

    def _parse_post_from_browser_html(self, html: str, shortcode: str, username: str) -> Optional[InstagramPost]:
        """Parse post from browser HTML as fallback"""
        try:
            # Extract caption
            caption_match = re.search(r'<meta property="og:description" content="([^"]*)"', html)
            caption = caption_match.group(1) if caption_match else ''

            # Extract media URL
            media_match = re.search(r'<meta property="og:image" content="([^"]*)"', html)
            media_url = media_match.group(1) if media_match else ''

            # Extract video URL if present
            video_match = re.search(r'<meta property="og:video" content="([^"]*)"', html)
            is_video = bool(video_match)
            if is_video:
                media_url = video_match.group(1)

            # Extract likes (approximate from HTML)
            likes_match = re.search(r'(\d+(?:,\d+)*)\s*(?:like|likes)', html, re.I)
            likes = int(likes_match.group(1).replace(',', '')) if likes_match else 0

            # Extract comments count
            comments_match = re.search(r'(\d+(?:,\d+)*)\s*(?:comment|comments)', html, re.I)
            comments_count = int(comments_match.group(1).replace(',', '')) if comments_match else 0

            post = InstagramPost(
                shortcode=shortcode,
                post_url=f"{self.base_url}/p/{shortcode}/",
                media_type='video' if is_video else 'image',
                media_urls=[media_url] if media_url else [],
                caption=caption,
                likes=likes,
                comments_count=comments_count,
                timestamp=datetime.now(),  # Can't extract without GraphQL
                is_video=is_video,
                owner_username=username
            )

            return post

        except Exception as e:
            logger.debug(f"Error parsing post from browser HTML: {e}")
            return None

    async def _scrape_comments_batch(
        self,
        posts: List[InstagramPost],
        max_comments: int
    ) -> List[InstagramPost]:
        """Scrape comments for multiple posts"""
        logger.info(f"Scraping comments for {len(posts)} posts...")

        # Scrape comments in parallel (with concurrency limit)
        tasks = []
        for post in posts:
            task = self._scrape_post_comments(post, max_comments)
            tasks.append(task)

        # Run 3 at a time to avoid rate limits
        results = []
        for i in range(0, len(tasks), 3):
            batch = tasks[i:i+3]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            results.extend(batch_results)

        # Filter out errors
        posts_with_comments = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error scraping comments: {result}")
            elif result:
                posts_with_comments.append(result)

        return posts_with_comments

    async def _scrape_post_comments(
        self,
        post: InstagramPost,
        max_comments: int
    ) -> InstagramPost:
        """Scrape comments for a single post using GraphQL"""
        await self.rate_limit()

        logger.info(f"Scraping comments for post: {post.shortcode}")

        # GraphQL query hash for comments (changes periodically)
        query_hash = "bc3296d1ce80a24b1b6e40b1e72903f5"  # May need updating

        variables = {
            "shortcode": post.shortcode,
            "first": min(max_comments, 50)
        }

        url = f"{self.base_url}/graphql/query/?query_hash={query_hash}&variables={json.dumps(variables)}"

        headers = {
            'x-ig-app-id': '936619743392459',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }

        proxy = await self.get_proxy()
        comments = []

        # StealthyFetcher is synchronous, not async
            try:
                fetcher = StealthyFetcher(proxy=proxy, headers=headers)
                response = fetcher.get(url)

                if response.status != 200:
                    logger.warning(f"Failed to fetch comments: {response.status}")
                    return post

                data = json.loads(response.text)

                # Extract comment edges
                media_data = data.get('data', {}).get('shortcode_media', {})
                comment_edges = media_data.get('edge_media_to_parent_comment', {}).get('edges', [])

                for edge in comment_edges:
                    try:
                        node = edge.get('node', {})
                        comment = self._parse_comment_from_graphql(node)
                        if comment:
                            comments.append(comment)
                    except Exception as e:
                        logger.debug(f"Error parsing comment: {e}")
                        continue

                # Handle pagination if we need more comments
                if len(comments) < max_comments:
                    page_info = media_data.get('edge_media_to_parent_comment', {}).get('page_info', {})
                    if page_info.get('has_next_page'):
                        end_cursor = page_info.get('end_cursor')
                        more_comments = await self._fetch_paginated_comments(
                            post.shortcode,
                            end_cursor,
                            max_comments - len(comments)
                        )
                        comments.extend(more_comments)

                post.comments = comments
                logger.info(f"Scraped {len(comments)} comments for post {post.shortcode}")

                if proxy and self.proxy_manager:
                    self.proxy_manager.report_success(proxy)

            except Exception as e:
                logger.error(f"Error scraping comments for post {post.shortcode}: {e}")
                if proxy and self.proxy_manager:
                    self.proxy_manager.report_failure(proxy)

        return post

    async def _fetch_paginated_comments(
        self,
        shortcode: str,
        end_cursor: str,
        max_comments: int
    ) -> List[InstagramComment]:
        """Fetch paginated comments using GraphQL"""
        await self.rate_limit()

        query_hash = "bc3296d1ce80a24b1b6e40b1e72903f5"  # May need updating

        variables = {
            "shortcode": shortcode,
            "first": min(max_comments, 50),
            "after": end_cursor
        }

        url = f"{self.base_url}/graphql/query/?query_hash={query_hash}&variables={json.dumps(variables)}"

        headers = {
            'x-ig-app-id': '936619743392459',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }

        proxy = await self.get_proxy()
        comments = []

        # StealthyFetcher is synchronous, not async
            try:
                fetcher = StealthyFetcher(proxy=proxy, headers=headers)
                response = fetcher.get(url)
                data = json.loads(response.text)

                edges = data.get('data', {}).get('shortcode_media', {}).get('edge_media_to_parent_comment', {}).get('edges', [])

                for edge in edges:
                    try:
                        node = edge.get('node', {})
                        comment = self._parse_comment_from_graphql(node)
                        if comment:
                            comments.append(comment)
                    except Exception as e:
                        logger.debug(f"Error parsing paginated comment: {e}")
                        continue

            except Exception as e:
                logger.warning(f"Comment pagination failed: {e}")

        return comments

    def _parse_comment_from_graphql(self, node: Dict[str, Any]) -> Optional[InstagramComment]:
        """Parse comment from GraphQL node data"""
        try:
            comment_id = node.get('id', '')
            if not comment_id:
                return None

            # Extract comment text
            text = node.get('text', '')

            # Extract author info
            owner = node.get('owner', {})
            author_username = owner.get('username', '')

            # Extract likes
            likes = node.get('edge_liked_by', {}).get('count', 0)

            # Extract timestamp
            timestamp = datetime.fromtimestamp(node.get('created_at', 0))

            comment = InstagramComment(
                comment_id=comment_id,
                text=text,
                author_username=author_username,
                likes=likes,
                timestamp=timestamp
            )

            return comment

        except Exception as e:
            logger.debug(f"Error parsing comment from GraphQL: {e}")
            return None
