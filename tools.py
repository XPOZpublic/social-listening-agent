import json

from xpoz import XpozClient

PLATFORMS = ("twitter", "reddit", "instagram", "tiktok")

POST_FIELDS = {
    "twitter": ["id", "text", "author_username", "like_count", "reply_count", "retweet_count", "created_at_date"],
    "reddit": ["id", "title", "selftext", "author_username", "subreddit_name", "score", "comments_count", "post_url", "permalink", "created_at_date"],
    "instagram": ["id", "caption", "username", "like_count", "comment_count", "code_url", "created_at_date"],
    "tiktok": ["id", "description", "username", "like_count", "comment_count", "play_count", "created_at_date"],
}

TOOL_DEFINITIONS = [
    {
        "name": "search_posts",
        "description": (
            "Search public posts on one platform by keyword. Supports exact phrases in double quotes "
            "and AND / OR / NOT operators. Returns normalized posts with author, text, engagement, date, and url."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "enum": list(PLATFORMS)},
                "query": {"type": "string", "description": "Search query, for example '\"espresso machine\" AND (broken OR refund)'"},
                "start_date": {"type": "string", "description": "YYYY-MM-DD, inclusive"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD, inclusive"},
                "limit": {"type": "integer", "description": "Maximum posts to return", "minimum": 1, "maximum": 100},
            },
            "required": ["platform", "query"],
        },
    },
    {
        "name": "get_comments",
        "description": "Fetch the comments or replies on one post, to read how people reacted to it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "enum": list(PLATFORMS)},
                "post_id": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["platform", "post_id"],
        },
    },
]


def search_posts(client: XpozClient, platform: str, query: str, start_date: str | None, end_date: str | None, limit: int) -> list[dict]:
    namespace = getattr(client, platform)
    result = namespace.search_posts(query, start_date=start_date, end_date=end_date, limit=limit, fields=POST_FIELDS[platform])
    return [normalize_post(platform, post) for post in result.data]


def get_comments(client: XpozClient, platform: str, post_id: str, limit: int) -> list[dict]:
    if platform == "reddit":
        comments = client.reddit.get_post_with_comments(post_id).comments
    else:
        comments = getattr(client, platform).get_comments(post_id).data
    return [normalize_comment(platform, comment) for comment in comments[:limit]]


def normalize_post(platform: str, post) -> dict:
    if platform == "twitter":
        return {
            "platform": platform,
            "id": post.id,
            "author": post.author_username,
            "text": post.text,
            "likes": post.like_count,
            "replies": post.reply_count,
            "reposts": post.retweet_count,
            "date": post.created_at_date,
            "url": f"https://x.com/{post.author_username}/status/{post.id}",
        }
    if platform == "reddit":
        return {
            "platform": platform,
            "id": post.id,
            "author": post.author_username,
            "subreddit": post.subreddit_name,
            "text": " ".join(part for part in (post.title, post.selftext) if part),
            "score": post.score,
            "replies": post.comments_count,
            "date": post.created_at_date,
            "url": post.post_url or f"https://www.reddit.com{post.permalink or ''}",
        }
    if platform == "instagram":
        return {
            "platform": platform,
            "id": post.id,
            "author": post.username,
            "text": post.caption,
            "likes": post.like_count,
            "replies": post.comment_count,
            "date": post.created_at_date,
            "url": post.code_url,
        }
    return {
        "platform": platform,
        "id": post.id,
        "author": post.username,
        "text": post.description,
        "likes": post.like_count,
        "replies": post.comment_count,
        "plays": post.play_count,
        "date": post.created_at_date,
        "url": f"https://www.tiktok.com/@{post.username}/video/{post.id}",
    }


def normalize_comment(platform: str, comment) -> dict:
    text = comment.body if platform == "reddit" else comment.text
    author = comment.author_username if platform == "reddit" else comment.username
    return {
        "platform": platform,
        "id": comment.id,
        "author": author,
        "text": text,
        "likes": getattr(comment, "like_count", None) or getattr(comment, "score", None),
        "date": comment.created_at_date,
    }


def run_tool(client: XpozClient, name: str, arguments: dict) -> str:
    limit = int(arguments.get("limit") or 20)
    if name == "search_posts":
        rows = search_posts(client, arguments["platform"], arguments["query"], arguments.get("start_date"), arguments.get("end_date"), limit)
    elif name == "get_comments":
        rows = get_comments(client, arguments["platform"], arguments["post_id"], limit)
    else:
        raise ValueError(f"unknown tool {name}")
    return json.dumps(rows, ensure_ascii=False, default=str)
