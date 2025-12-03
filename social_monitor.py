#!/usr/bin/env python3
"""
SHADOW Social Media Monitor
Real-time monitoring of X (Twitter), Reddit, YouTube, News, Bluesky, Mastodon
Tracks names, subjects, and entities across social platforms
"""

import os
import re
import json
import time
import asyncio
import hashlib
import sqlite3
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Callable, Set
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode, quote
import logging
import websockets
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============ CONFIGURATION ============
CONFIG = {
    "database_path": "social_monitor.db",
    "poll_interval": 60,  # seconds between polls
    "max_results_per_query": 100,
    
    # API Keys (set via environment variables)
    "twitter_bearer_token": os.environ.get("TWITTER_BEARER_TOKEN", ""),
    "reddit_client_id": os.environ.get("REDDIT_CLIENT_ID", ""),
    "reddit_client_secret": os.environ.get("REDDIT_CLIENT_SECRET", ""),
    "youtube_api_key": os.environ.get("YOUTUBE_API_KEY", ""),
    "newsapi_key": os.environ.get("NEWSAPI_KEY", ""),
    
    # User agent for scraping
    "user_agent": "SHADOW-Monitor/1.0 (Research; github.com/shadow-project)",
}

# ============ DATA MODELS ============
@dataclass
class SocialPost:
    """Represents a social media post"""
    id: str
    platform: str  # twitter, reddit, youtube, news, bluesky, mastodon
    post_type: str  # tweet, comment, video, article
    
    # Content
    author: str
    author_id: Optional[str] = None
    content: str = ""
    title: Optional[str] = None
    url: str = ""
    media_urls: Optional[List[str]] = None
    
    # Metadata
    created_at: str = ""
    collected_at: str = ""
    likes: int = 0
    shares: int = 0
    comments: int = 0
    views: int = 0
    
    # Matching info
    matched_queries: Optional[List[str]] = None
    matched_entities: Optional[List[str]] = None
    sentiment: Optional[str] = None
    
    # Raw data
    raw_data: Optional[Dict] = None


@dataclass
class MonitorQuery:
    """A query to monitor"""
    id: str
    name: str
    query_type: str  # keyword, hashtag, user, entity
    query: str
    platforms: List[str]
    enabled: bool = True
    created_at: str = ""
    last_checked: Optional[str] = None
    
    # Filters
    min_engagement: int = 0
    exclude_retweets: bool = False
    language: str = "en"


# ============ DATABASE ============
def init_monitor_db(db_path: str) -> sqlite3.Connection:
    """Initialize social monitor database"""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Monitor queries table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monitor_queries (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            query_type TEXT NOT NULL,
            query TEXT NOT NULL,
            platforms TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            created_at TEXT,
            last_checked TEXT,
            min_engagement INTEGER DEFAULT 0,
            exclude_retweets INTEGER DEFAULT 0,
            language TEXT DEFAULT 'en',
            metadata TEXT
        )
    """)
    
    # Social posts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS social_posts (
            id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            post_type TEXT NOT NULL,
            author TEXT,
            author_id TEXT,
            content TEXT,
            title TEXT,
            url TEXT,
            media_urls TEXT,
            created_at TEXT,
            collected_at TEXT,
            likes INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            views INTEGER DEFAULT 0,
            matched_queries TEXT,
            matched_entities TEXT,
            sentiment TEXT,
            raw_data TEXT,
            processed INTEGER DEFAULT 0
        )
    """)
    
    # Alerts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY,
            post_id TEXT,
            query_id TEXT,
            alert_type TEXT,
            message TEXT,
            severity TEXT,
            created_at TEXT,
            acknowledged INTEGER DEFAULT 0,
            FOREIGN KEY (post_id) REFERENCES social_posts(id),
            FOREIGN KEY (query_id) REFERENCES monitor_queries(id)
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_platform ON social_posts(platform)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_created ON social_posts(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_author ON social_posts(author)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_unack ON alerts(acknowledged)")
    
    # Full-text search
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
            content, title, author,
            content='social_posts',
            content_rowid='rowid'
        )
    """)
    
    conn.commit()
    return conn


# ============ PLATFORM SCRAPERS ============

class TwitterMonitor:
    """Monitor X/Twitter using API or scraping"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.bearer_token = config.get("twitter_bearer_token", "")
        self.base_url = "https://api.twitter.com/2"
        
    def search(self, query: str, max_results: int = 100) -> List[SocialPost]:
        """Search Twitter using API"""
        if not self.bearer_token:
            logger.warning("Twitter API token not configured, using Nitter fallback")
            return self.search_nitter(query, max_results)
        
        posts = []
        try:
            headers = {"Authorization": f"Bearer {self.bearer_token}"}
            params = {
                "query": query,
                "max_results": min(max_results, 100),
                "tweet.fields": "created_at,public_metrics,author_id,entities",
                "expansions": "author_id",
                "user.fields": "username,name"
            }
            
            response = requests.get(
                f"{self.base_url}/tweets/search/recent",
                headers=headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
                
                for tweet in data.get("data", []):
                    author_id = tweet.get("author_id", "")
                    author = users.get(author_id, {}).get("username", "unknown")
                    metrics = tweet.get("public_metrics", {})
                    
                    posts.append(SocialPost(
                        id=f"twitter_{tweet['id']}",
                        platform="twitter",
                        post_type="tweet",
                        author=author,
                        author_id=author_id,
                        content=tweet.get("text", ""),
                        url=f"https://twitter.com/{author}/status/{tweet['id']}",
                        created_at=tweet.get("created_at", ""),
                        collected_at=datetime.now().isoformat(),
                        likes=metrics.get("like_count", 0),
                        shares=metrics.get("retweet_count", 0),
                        comments=metrics.get("reply_count", 0),
                        views=metrics.get("impression_count", 0),
                        matched_queries=[query],
                        raw_data=tweet
                    ))
            else:
                logger.error(f"Twitter API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Twitter search error: {e}")
        
        return posts
    
    def search_nitter(self, query: str, max_results: int = 50) -> List[SocialPost]:
        """Fallback: Search using Nitter instances"""
        posts = []
        nitter_instances = [
            "https://nitter.net",
            "https://nitter.privacydev.net",
            "https://nitter.poast.org",
        ]
        
        for instance in nitter_instances:
            try:
                url = f"{instance}/search?f=tweets&q={quote(query)}"
                response = requests.get(
                    url,
                    headers={"User-Agent": self.config["user_agent"]},
                    timeout=15
                )
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    for tweet in soup.select('.timeline-item')[:max_results]:
                        try:
                            username = tweet.select_one('.username')
                            content = tweet.select_one('.tweet-content')
                            link = tweet.select_one('.tweet-link')
                            stats = tweet.select('.tweet-stat')
                            
                            if username and content:
                                tweet_id = hashlib.md5(
                                    f"{username.get_text()}{content.get_text()[:100]}".encode()
                                ).hexdigest()[:16]
                                
                                posts.append(SocialPost(
                                    id=f"twitter_{tweet_id}",
                                    platform="twitter",
                                    post_type="tweet",
                                    author=username.get_text(strip=True).replace('@', ''),
                                    content=content.get_text(strip=True),
                                    url=f"https://twitter.com{link.get('href', '')}" if link else "",
                                    collected_at=datetime.now().isoformat(),
                                    matched_queries=[query]
                                ))
                        except Exception as e:
                            continue
                    
                    if posts:
                        break  # Success, no need to try other instances
                        
            except Exception as e:
                logger.debug(f"Nitter {instance} failed: {e}")
                continue
        
        return posts
    
    def get_user_tweets(self, username: str, max_results: int = 50) -> List[SocialPost]:
        """Get tweets from a specific user"""
        return self.search(f"from:{username}", max_results)


class RedditMonitor:
    """Monitor Reddit"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.client_id = config.get("reddit_client_id", "")
        self.client_secret = config.get("reddit_client_secret", "")
        self.access_token = None
        self.token_expires = None
        
    def authenticate(self):
        """Get Reddit OAuth token"""
        if not self.client_id or not self.client_secret:
            return False
        
        try:
            auth = requests.auth.HTTPBasicAuth(self.client_id, self.client_secret)
            data = {"grant_type": "client_credentials"}
            headers = {"User-Agent": self.config["user_agent"]}
            
            response = requests.post(
                "https://www.reddit.com/api/v1/access_token",
                auth=auth,
                data=data,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data["access_token"]
                self.token_expires = datetime.now() + timedelta(seconds=token_data["expires_in"] - 60)
                return True
        except Exception as e:
            logger.error(f"Reddit auth error: {e}")
        
        return False
    
    def search(self, query: str, subreddit: str = None, max_results: int = 100) -> List[SocialPost]:
        """Search Reddit posts"""
        posts = []
        
        # Try API first, fall back to JSON endpoints
        if self.access_token and self.token_expires > datetime.now():
            posts = self._search_api(query, subreddit, max_results)
        
        if not posts:
            posts = self._search_json(query, subreddit, max_results)
        
        return posts
    
    def _search_api(self, query: str, subreddit: str, max_results: int) -> List[SocialPost]:
        """Search using Reddit API"""
        posts = []
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "User-Agent": self.config["user_agent"]
            }
            
            url = f"https://oauth.reddit.com/search"
            if subreddit:
                url = f"https://oauth.reddit.com/r/{subreddit}/search"
            
            params = {
                "q": query,
                "limit": min(max_results, 100),
                "sort": "new",
                "t": "week"
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                for post in data.get("data", {}).get("children", []):
                    p = post.get("data", {})
                    posts.append(self._parse_post(p, query))
                    
        except Exception as e:
            logger.error(f"Reddit API error: {e}")
        
        return posts
    
    def _search_json(self, query: str, subreddit: str, max_results: int) -> List[SocialPost]:
        """Search using Reddit JSON endpoints (no auth needed)"""
        posts = []
        try:
            if subreddit:
                url = f"https://www.reddit.com/r/{subreddit}/search.json"
            else:
                url = "https://www.reddit.com/search.json"
            
            params = {
                "q": query,
                "limit": min(max_results, 100),
                "sort": "new",
                "t": "week"
            }
            
            response = requests.get(
                url,
                params=params,
                headers={"User-Agent": self.config["user_agent"]},
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                for post in data.get("data", {}).get("children", []):
                    p = post.get("data", {})
                    posts.append(self._parse_post(p, query))
                    
        except Exception as e:
            logger.error(f"Reddit JSON error: {e}")
        
        return posts
    
    def _parse_post(self, data: Dict, query: str) -> SocialPost:
        """Parse Reddit post data"""
        return SocialPost(
            id=f"reddit_{data.get('id', '')}",
            platform="reddit",
            post_type="post" if data.get("is_self") else "link",
            author=data.get("author", "[deleted]"),
            author_id=data.get("author_fullname"),
            content=data.get("selftext", "") or data.get("title", ""),
            title=data.get("title", ""),
            url=f"https://reddit.com{data.get('permalink', '')}",
            created_at=datetime.fromtimestamp(data.get("created_utc", 0)).isoformat(),
            collected_at=datetime.now().isoformat(),
            likes=data.get("score", 0),
            comments=data.get("num_comments", 0),
            matched_queries=[query],
            raw_data=data
        )
    
    def monitor_subreddit(self, subreddit: str, max_results: int = 25) -> List[SocialPost]:
        """Get latest posts from a subreddit"""
        posts = []
        try:
            url = f"https://www.reddit.com/r/{subreddit}/new.json"
            response = requests.get(
                url,
                params={"limit": max_results},
                headers={"User-Agent": self.config["user_agent"]},
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                for post in data.get("data", {}).get("children", []):
                    p = post.get("data", {})
                    posts.append(self._parse_post(p, f"r/{subreddit}"))
                    
        except Exception as e:
            logger.error(f"Reddit subreddit error: {e}")
        
        return posts


class YouTubeMonitor:
    """Monitor YouTube"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.api_key = config.get("youtube_api_key", "")
        self.base_url = "https://www.googleapis.com/youtube/v3"
    
    def search(self, query: str, max_results: int = 50) -> List[SocialPost]:
        """Search YouTube videos"""
        posts = []
        
        if not self.api_key:
            logger.warning("YouTube API key not configured")
            return posts
        
        try:
            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": min(max_results, 50),
                "order": "date",
                "key": self.api_key
            }
            
            response = requests.get(
                f"{self.base_url}/search",
                params=params,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Get video statistics
                video_ids = [item["id"]["videoId"] for item in data.get("items", [])]
                stats = self._get_video_stats(video_ids)
                
                for item in data.get("items", []):
                    video_id = item["id"]["videoId"]
                    snippet = item.get("snippet", {})
                    video_stats = stats.get(video_id, {})
                    
                    posts.append(SocialPost(
                        id=f"youtube_{video_id}",
                        platform="youtube",
                        post_type="video",
                        author=snippet.get("channelTitle", ""),
                        author_id=snippet.get("channelId", ""),
                        content=snippet.get("description", ""),
                        title=snippet.get("title", ""),
                        url=f"https://youtube.com/watch?v={video_id}",
                        media_urls=[snippet.get("thumbnails", {}).get("high", {}).get("url", "")],
                        created_at=snippet.get("publishedAt", ""),
                        collected_at=datetime.now().isoformat(),
                        likes=int(video_stats.get("likeCount", 0)),
                        views=int(video_stats.get("viewCount", 0)),
                        comments=int(video_stats.get("commentCount", 0)),
                        matched_queries=[query],
                        raw_data=item
                    ))
                    
        except Exception as e:
            logger.error(f"YouTube search error: {e}")
        
        return posts
    
    def _get_video_stats(self, video_ids: List[str]) -> Dict:
        """Get statistics for videos"""
        stats = {}
        
        if not video_ids:
            return stats
        
        try:
            params = {
                "part": "statistics",
                "id": ",".join(video_ids),
                "key": self.api_key
            }
            
            response = requests.get(
                f"{self.base_url}/videos",
                params=params,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                for item in data.get("items", []):
                    stats[item["id"]] = item.get("statistics", {})
                    
        except Exception as e:
            logger.error(f"YouTube stats error: {e}")
        
        return stats


class NewsMonitor:
    """Monitor news sources via NewsAPI and RSS"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.api_key = config.get("newsapi_key", "")
        
        # Major news RSS feeds
        self.rss_feeds = {
            "reuters": "https://feeds.reuters.com/reuters/topNews",
            "ap": "https://rsshub.app/apnews/topics/apf-topnews",
            "bbc": "http://feeds.bbci.co.uk/news/rss.xml",
            "nyt": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
            "guardian": "https://www.theguardian.com/world/rss",
            "wapo": "http://feeds.washingtonpost.com/rss/politics",
            "politico": "https://www.politico.com/rss/politicopicks.xml",
        }
    
    def search(self, query: str, max_results: int = 100) -> List[SocialPost]:
        """Search news articles"""
        posts = []
        
        # Try NewsAPI first
        if self.api_key:
            posts.extend(self._search_newsapi(query, max_results))
        
        # Also search RSS feeds
        posts.extend(self._search_rss(query, max_results // 2))
        
        return posts
    
    def _search_newsapi(self, query: str, max_results: int) -> List[SocialPost]:
        """Search using NewsAPI"""
        posts = []
        
        try:
            params = {
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": min(max_results, 100),
                "apiKey": self.api_key
            }
            
            response = requests.get(
                "https://newsapi.org/v2/everything",
                params=params,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                
                for article in data.get("articles", []):
                    article_id = hashlib.md5(article.get("url", "").encode()).hexdigest()[:16]
                    
                    posts.append(SocialPost(
                        id=f"news_{article_id}",
                        platform="news",
                        post_type="article",
                        author=article.get("author") or article.get("source", {}).get("name", ""),
                        content=article.get("description", "") or article.get("content", ""),
                        title=article.get("title", ""),
                        url=article.get("url", ""),
                        media_urls=[article.get("urlToImage")] if article.get("urlToImage") else None,
                        created_at=article.get("publishedAt", ""),
                        collected_at=datetime.now().isoformat(),
                        matched_queries=[query],
                        raw_data=article
                    ))
                    
        except Exception as e:
            logger.error(f"NewsAPI error: {e}")
        
        return posts
    
    def _search_rss(self, query: str, max_results: int) -> List[SocialPost]:
        """Search RSS feeds"""
        posts = []
        query_lower = query.lower()
        
        try:
            import feedparser
        except ImportError:
            logger.warning("feedparser not installed, skipping RSS")
            return posts
        
        for source, feed_url in self.rss_feeds.items():
            try:
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:max_results // len(self.rss_feeds)]:
                    # Check if query matches
                    title = entry.get("title", "").lower()
                    summary = entry.get("summary", "").lower()
                    
                    if query_lower in title or query_lower in summary:
                        article_id = hashlib.md5(entry.get("link", "").encode()).hexdigest()[:16]
                        
                        posts.append(SocialPost(
                            id=f"news_{source}_{article_id}",
                            platform="news",
                            post_type="article",
                            author=source.upper(),
                            content=entry.get("summary", ""),
                            title=entry.get("title", ""),
                            url=entry.get("link", ""),
                            created_at=entry.get("published", ""),
                            collected_at=datetime.now().isoformat(),
                            matched_queries=[query]
                        ))
                        
            except Exception as e:
                logger.debug(f"RSS {source} error: {e}")
        
        return posts


class BlueskyMonitor:
    """Monitor Bluesky"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.base_url = "https://public.api.bsky.app/xrpc"
    
    def search(self, query: str, max_results: int = 50) -> List[SocialPost]:
        """Search Bluesky posts"""
        posts = []
        
        try:
            params = {
                "q": query,
                "limit": min(max_results, 100)
            }
            
            response = requests.get(
                f"{self.base_url}/app.bsky.feed.searchPosts",
                params=params,
                headers={"User-Agent": self.config["user_agent"]},
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                
                for post in data.get("posts", []):
                    author = post.get("author", {})
                    record = post.get("record", {})
                    
                    posts.append(SocialPost(
                        id=f"bluesky_{post.get('uri', '').split('/')[-1]}",
                        platform="bluesky",
                        post_type="post",
                        author=author.get("handle", ""),
                        author_id=author.get("did", ""),
                        content=record.get("text", ""),
                        url=f"https://bsky.app/profile/{author.get('handle', '')}/post/{post.get('uri', '').split('/')[-1]}",
                        created_at=record.get("createdAt", ""),
                        collected_at=datetime.now().isoformat(),
                        likes=post.get("likeCount", 0),
                        shares=post.get("repostCount", 0),
                        comments=post.get("replyCount", 0),
                        matched_queries=[query],
                        raw_data=post
                    ))
                    
        except Exception as e:
            logger.error(f"Bluesky search error: {e}")
        
        return posts


class MastodonMonitor:
    """Monitor Mastodon/Fediverse"""
    
    def __init__(self, config: Dict):
        self.config = config
        # Public Mastodon instances
        self.instances = [
            "https://mastodon.social",
            "https://mas.to",
            "https://fosstodon.org",
        ]
    
    def search(self, query: str, max_results: int = 50) -> List[SocialPost]:
        """Search Mastodon posts across instances"""
        posts = []
        
        for instance in self.instances:
            try:
                response = requests.get(
                    f"{instance}/api/v2/search",
                    params={"q": query, "type": "statuses", "limit": max_results // len(self.instances)},
                    headers={"User-Agent": self.config["user_agent"]},
                    timeout=15
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    for status in data.get("statuses", []):
                        account = status.get("account", {})
                        
                        # Strip HTML from content
                        content = BeautifulSoup(status.get("content", ""), "html.parser").get_text()
                        
                        posts.append(SocialPost(
                            id=f"mastodon_{status.get('id', '')}",
                            platform="mastodon",
                            post_type="toot",
                            author=account.get("acct", ""),
                            author_id=account.get("id", ""),
                            content=content,
                            url=status.get("url", ""),
                            created_at=status.get("created_at", ""),
                            collected_at=datetime.now().isoformat(),
                            likes=status.get("favourites_count", 0),
                            shares=status.get("reblogs_count", 0),
                            comments=status.get("replies_count", 0),
                            matched_queries=[query],
                            raw_data=status
                        ))
                        
            except Exception as e:
                logger.debug(f"Mastodon {instance} error: {e}")
        
        return posts


# ============ MAIN MONITOR ============
class SocialMonitor:
    """Main social media monitoring orchestrator"""
    
    def __init__(self, config: Dict = None):
        self.config = config or CONFIG
        self.conn = init_monitor_db(self.config["database_path"])
        
        # Initialize platform monitors
        self.platforms = {
            "twitter": TwitterMonitor(self.config),
            "reddit": RedditMonitor(self.config),
            "youtube": YouTubeMonitor(self.config),
            "news": NewsMonitor(self.config),
            "bluesky": BlueskyMonitor(self.config),
            "mastodon": MastodonMonitor(self.config),
        }
        
        # Callbacks for real-time updates
        self.callbacks: List[Callable[[SocialPost], None]] = []
        
        # Running state
        self.running = False
    
    def add_callback(self, callback: Callable[[SocialPost], None]):
        """Add callback for new posts"""
        self.callbacks.append(callback)
    
    def add_query(self, name: str, query: str, query_type: str = "keyword",
                  platforms: List[str] = None) -> str:
        """Add a new monitoring query"""
        query_id = hashlib.md5(f"{name}_{query}_{datetime.now().isoformat()}".encode()).hexdigest()[:16]
        
        if platforms is None:
            platforms = list(self.platforms.keys())
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO monitor_queries (id, name, query_type, query, platforms, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (query_id, name, query_type, query, json.dumps(platforms), datetime.now().isoformat()))
        self.conn.commit()
        
        logger.info(f"Added query: {name} ({query})")
        return query_id
    
    def remove_query(self, query_id: str):
        """Remove a monitoring query"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM monitor_queries WHERE id = ?", (query_id,))
        self.conn.commit()
    
    def get_queries(self) -> List[Dict]:
        """Get all monitoring queries"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM monitor_queries WHERE enabled = 1")
        return [dict(row) for row in cursor.fetchall()]
    
    def save_post(self, post: SocialPost):
        """Save a post to the database"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO social_posts (
                    id, platform, post_type, author, author_id, content, title, url,
                    media_urls, created_at, collected_at, likes, shares, comments, views,
                    matched_queries, matched_entities, sentiment, raw_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                post.id, post.platform, post.post_type, post.author, post.author_id,
                post.content, post.title, post.url,
                json.dumps(post.media_urls) if post.media_urls else None,
                post.created_at, post.collected_at, post.likes, post.shares,
                post.comments, post.views,
                json.dumps(post.matched_queries) if post.matched_queries else None,
                json.dumps(post.matched_entities) if post.matched_entities else None,
                post.sentiment,
                json.dumps(post.raw_data) if post.raw_data else None
            ))
            
            # Add to FTS index
            cursor.execute("""
                INSERT OR REPLACE INTO posts_fts (rowid, content, title, author)
                SELECT rowid, content, title, author FROM social_posts WHERE id = ?
            """, (post.id,))
            
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"Error saving post: {e}")
    
    def search_posts(self, query: str, platforms: List[str] = None,
                     limit: int = 100) -> List[SocialPost]:
        """Search all monitored posts"""
        cursor = self.conn.cursor()
        
        sql = """
            SELECT p.* FROM social_posts p
            JOIN posts_fts fts ON p.rowid = fts.rowid
            WHERE posts_fts MATCH ?
        """
        params = [query]
        
        if platforms:
            sql += f" AND p.platform IN ({','.join('?' * len(platforms))})"
            params.extend(platforms)
        
        sql += " ORDER BY p.created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(sql, params)
        return [self._row_to_post(row) for row in cursor.fetchall()]
    
    def _row_to_post(self, row: sqlite3.Row) -> SocialPost:
        """Convert database row to SocialPost"""
        return SocialPost(
            id=row["id"],
            platform=row["platform"],
            post_type=row["post_type"],
            author=row["author"],
            author_id=row["author_id"],
            content=row["content"],
            title=row["title"],
            url=row["url"],
            media_urls=json.loads(row["media_urls"]) if row["media_urls"] else None,
            created_at=row["created_at"],
            collected_at=row["collected_at"],
            likes=row["likes"],
            shares=row["shares"],
            comments=row["comments"],
            views=row["views"],
            matched_queries=json.loads(row["matched_queries"]) if row["matched_queries"] else None,
            matched_entities=json.loads(row["matched_entities"]) if row["matched_entities"] else None,
            sentiment=row["sentiment"]
        )
    
    async def run_once(self):
        """Run one monitoring cycle"""
        queries = self.get_queries()
        
        for query_data in queries:
            query = query_data["query"]
            platforms = json.loads(query_data["platforms"])
            
            for platform_name in platforms:
                if platform_name not in self.platforms:
                    continue
                
                platform = self.platforms[platform_name]
                
                try:
                    posts = platform.search(query)
                    
                    for post in posts:
                        # Check if new
                        cursor = self.conn.cursor()
                        cursor.execute("SELECT id FROM social_posts WHERE id = ?", (post.id,))
                        
                        if not cursor.fetchone():
                            self.save_post(post)
                            
                            # Trigger callbacks
                            for callback in self.callbacks:
                                try:
                                    callback(post)
                                except Exception as e:
                                    logger.error(f"Callback error: {e}")
                            
                            logger.info(f"New post: [{post.platform}] @{post.author}: {post.content[:50]}...")
                            
                except Exception as e:
                    logger.error(f"Error monitoring {platform_name} for '{query}': {e}")
            
            # Update last checked
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE monitor_queries SET last_checked = ? WHERE id = ?",
                (datetime.now().isoformat(), query_data["id"])
            )
            self.conn.commit()
    
    async def run(self):
        """Run continuous monitoring"""
        self.running = True
        logger.info("Starting social media monitor...")
        
        while self.running:
            await self.run_once()
            await asyncio.sleep(self.config["poll_interval"])
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
    
    def get_stats(self) -> Dict:
        """Get monitoring statistics"""
        cursor = self.conn.cursor()
        
        stats = {}
        
        cursor.execute("SELECT COUNT(*) FROM social_posts")
        stats["total_posts"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM monitor_queries WHERE enabled = 1")
        stats["active_queries"] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT platform, COUNT(*) as count 
            FROM social_posts 
            GROUP BY platform
        """)
        stats["posts_by_platform"] = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.execute("""
            SELECT COUNT(*) FROM social_posts 
            WHERE collected_at > datetime('now', '-24 hours')
        """)
        stats["posts_last_24h"] = cursor.fetchone()[0]
        
        return stats


# ============ WEBSOCKET SERVER FOR REAL-TIME UPDATES ============
class RealtimeServer:
    """WebSocket server for real-time updates to frontend"""
    
    def __init__(self, monitor: SocialMonitor, host: str = "localhost", port: int = 8765):
        self.monitor = monitor
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
    
    async def handler(self, websocket, path):
        """Handle WebSocket connections"""
        self.clients.add(websocket)
        try:
            async for message in websocket:
                # Handle incoming commands
                try:
                    data = json.loads(message)
                    await self.handle_command(websocket, data)
                except json.JSONDecodeError:
                    pass
        finally:
            self.clients.remove(websocket)
    
    async def handle_command(self, websocket, data: Dict):
        """Handle commands from clients"""
        command = data.get("command")
        
        if command == "add_query":
            query_id = self.monitor.add_query(
                data.get("name", ""),
                data.get("query", ""),
                data.get("query_type", "keyword"),
                data.get("platforms")
            )
            await websocket.send(json.dumps({"type": "query_added", "id": query_id}))
        
        elif command == "remove_query":
            self.monitor.remove_query(data.get("query_id", ""))
            await websocket.send(json.dumps({"type": "query_removed"}))
        
        elif command == "get_queries":
            queries = self.monitor.get_queries()
            await websocket.send(json.dumps({"type": "queries", "data": queries}))
        
        elif command == "search":
            posts = self.monitor.search_posts(
                data.get("query", ""),
                data.get("platforms"),
                data.get("limit", 100)
            )
            await websocket.send(json.dumps({
                "type": "search_results",
                "data": [asdict(p) for p in posts]
            }))
        
        elif command == "get_stats":
            stats = self.monitor.get_stats()
            await websocket.send(json.dumps({"type": "stats", "data": stats}))
    
    async def broadcast(self, message: Dict):
        """Broadcast message to all connected clients"""
        if self.clients:
            await asyncio.gather(
                *[client.send(json.dumps(message)) for client in self.clients]
            )
    
    def on_new_post(self, post: SocialPost):
        """Callback for new posts"""
        asyncio.create_task(self.broadcast({
            "type": "new_post",
            "data": asdict(post)
        }))
    
    async def run(self):
        """Run the WebSocket server"""
        # Register callback for new posts
        self.monitor.add_callback(self.on_new_post)
        
        async with websockets.serve(self.handler, self.host, self.port):
            logger.info(f"WebSocket server running on ws://{self.host}:{self.port}")
            await asyncio.Future()  # Run forever


# ============ CLI ============
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="SHADOW Social Media Monitor")
    subparsers = parser.add_subparsers(dest='command')
    
    # Add query
    add_parser = subparsers.add_parser('add', help='Add monitoring query')
    add_parser.add_argument('name', help='Query name')
    add_parser.add_argument('query', help='Search query')
    add_parser.add_argument('--type', default='keyword', help='Query type')
    add_parser.add_argument('--platforms', nargs='+', help='Platforms to monitor')
    
    # List queries
    list_parser = subparsers.add_parser('list', help='List monitoring queries')
    
    # Search
    search_parser = subparsers.add_parser('search', help='Search collected posts')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--platform', help='Filter by platform')
    search_parser.add_argument('--limit', type=int, default=20)
    
    # Run once
    once_parser = subparsers.add_parser('once', help='Run one monitoring cycle')
    
    # Run continuous
    run_parser = subparsers.add_parser('run', help='Run continuous monitoring')
    run_parser.add_argument('--websocket', action='store_true', help='Enable WebSocket server')
    run_parser.add_argument('--port', type=int, default=8765)
    
    # Stats
    stats_parser = subparsers.add_parser('stats', help='Show statistics')
    
    args = parser.parse_args()
    
    monitor = SocialMonitor()
    
    if args.command == 'add':
        query_id = monitor.add_query(args.name, args.query, args.type, args.platforms)
        print(f"Added query: {query_id}")
    
    elif args.command == 'list':
        queries = monitor.get_queries()
        print("\n=== Monitoring Queries ===\n")
        for q in queries:
            platforms = json.loads(q["platforms"])
            print(f"[{q['id'][:8]}] {q['name']}")
            print(f"  Query: {q['query']}")
            print(f"  Platforms: {', '.join(platforms)}")
            print(f"  Last checked: {q['last_checked'] or 'Never'}")
            print()
    
    elif args.command == 'search':
        platforms = [args.platform] if args.platform else None
        posts = monitor.search_posts(args.query, platforms, args.limit)
        
        print(f"\n=== Found {len(posts)} posts ===\n")
        for post in posts:
            print(f"[{post.platform}] @{post.author}")
            print(f"  {post.content[:100]}...")
            print(f"  URL: {post.url}")
            print(f"  {post.likes} likes, {post.shares} shares")
            print()
    
    elif args.command == 'once':
        await monitor.run_once()
        print("Completed one monitoring cycle")
    
    elif args.command == 'run':
        if args.websocket:
            server = RealtimeServer(monitor, port=args.port)
            await asyncio.gather(
                monitor.run(),
                server.run()
            )
        else:
            await monitor.run()
    
    elif args.command == 'stats':
        stats = monitor.get_stats()
        print("\n=== Social Monitor Statistics ===\n")
        print(f"Total posts collected: {stats['total_posts']}")
        print(f"Active queries: {stats['active_queries']}")
        print(f"Posts in last 24h: {stats['posts_last_24h']}")
        print("\nPosts by platform:")
        for platform, count in stats.get('posts_by_platform', {}).items():
            print(f"  {platform}: {count}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
