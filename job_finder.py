import os
import json
import html
import re
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import requests

SUBREDDITS = ["forhire", "slavelabour", "DoneDirtCheap"]

EASY_WIN_KEYWORDS = [
    "script", "bot", "automation", "automate", "scrape", "scraper",
    "python", "api", "tool", "browser automation", "simple website",
    "landing page", "fix bug", "debug", "small task", "quick task",
    "selenium", "playwright"
]

HIGH_VALUE_KEYWORDS = [
    "saas", "web app", "mobile app", "dashboard", "full stack",
    "full-stack", "ai app", "crm", "custom software", "platform",
    "booking system", "automation system", "integrate", "integration",
    "stripe", "backend", "frontend", "next.js", "react", "django",
    "node", "app developer"
]

BUDGET_HINTS = [
    "$", "budget", "pay", "paid", "hiring", "hire", "payment",
    "fixed price", "hourly", "/hr", "usd"
]

NEGATIVE_KEYWORDS = [
    "nsfw", "adult", "crypto scam", "gambling", "onlyfans"
]

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN_FILE = Path("seen_posts.json")


def load_seen():
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(sorted(list(seen)), indent=2), encoding="utf-8")


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = " ".join(value.split())
    return value.strip()


def escape_html(text: str) -> str:
    return html.escape(text or "")


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit - 1].rstrip() + "…"


def get_feed_urls():
    return [f"https://www.reddit.com/r/{sub}/new.rss" for sub in SUBREDDITS]


def classify_post(text: str):
    lower = text.lower()

    if any(bad in lower for bad in NEGATIVE_KEYWORDS):
        return None, [], 0

    easy_matches = [k for k in EASY_WIN_KEYWORDS if k in lower]
    high_matches = [k for k in HIGH_VALUE_KEYWORDS if k in lower]
    budget_matches = [k for k in BUDGET_HINTS if k in lower]

    score = 0
    score += min(len(easy_matches), 5) * 2
    score += min(len(high_matches), 5) * 3
    score += min(len(budget_matches), 3) * 2

    if high_matches:
        return "Higher Value", high_matches + budget_matches, score

    if easy_matches:
        return "Easy Win", easy_matches + budget_matches, score

    return None, [], score


def generate_replies(title: str, job_type: str):
    short_title = truncate(title, 90)

    if job_type == "Higher Value":
        return [
            "Hey — I can help build this. I work on custom tools, automations, and lightweight apps. If you send me the scope, budget, and deadline, I can tell you quickly if I’m a fit.",
            "This looks like something I can take on. I can move fast on builds like this, especially if you already know the main features you want. Feel free to DM the details.",
            f"I’m interested in this project. I build scripts, automations, and web tools, so '{short_title}' sounds in my lane. Send me the exact requirements and I’ll reply with a plan."
        ]

    return [
        "Hey — I can probably knock this out pretty quickly. I build scripts and automations, and this looks like a solid fit. What deadline and budget are you aiming for?",
        "I can help with this. I’ve handled similar small automation or script tasks before and can move fast. If you message me the exact task, I’ll tell you right away if I can do it.",
        "This looks like something I can take care of fast. Send over the details and I’ll reply with a quick turnaround estimate and price."
    ]


def send_message(text: str, buttons=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}

    response = requests.post(url, json=payload, timeout=20)
    response.raise_for_status()


def send_job_alert(subreddit: str, title: str, summary: str, link: str, job_type: str, matched_terms, score: int):
    emoji = "💰" if job_type == "Higher Value" else "⚡"

    safe_title = escape_html(truncate(title, 120))
    safe_summary = escape_html(truncate(summary, 140))
    safe_terms = escape_html(", ".join(matched_terms[:4]) if matched_terms else "match")

    main_text = (
        f"{emoji} <b>{escape_html(job_type)}</b>\n"
        f"<b>r/{escape_html(subreddit)}</b> • Score {score}\n\n"
        f"<b>{safe_title}</b>\n\n"
        f"{safe_summary}\n\n"
        f"<b>Tags:</b> {safe_terms}"
    )

    buttons = [
        [{"text": "Open Post", "url": link}]
    ]

    send_message(main_text, buttons=buttons)


def send_reply_options(replies):
    for i, reply in enumerate(replies, start=1):
        text = (
            f"<b>Reply {i}</b>\n\n"
            f"{escape_html(reply)}"
        )
        send_message(text)


def entry_id(entry):
    if getattr(entry, "id", None):
        return entry.id
    if getattr(entry, "link", None):
        return entry.link
    return getattr(entry, "title", "")


def run():
    if not TELEGRAM_TOKEN or not CHAT_ID:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")

    seen = load_seen()
    new_seen = set(seen)

    for feed_url in get_feed_urls():
        feed = feedparser.parse(feed_url)
        subreddit = urlparse(feed_url).path.split("/")[2]

        for entry in feed.entries[:20]:
            unique_id = entry_id(entry)
            if unique_id in seen:
                continue

            title = clean_text(getattr(entry, "title", ""))
            summary = clean_text(getattr(entry, "summary", ""))
            link = getattr(entry, "link", "")
            text = f"{title}\n{summary}"

            job_type, matched_terms, score = classify_post(text)

            if job_type:
                replies = generate_replies(title, job_type)
                send_job_alert(
                    subreddit=subreddit,
                    title=title,
                    summary=summary,
                    link=link,
                    job_type=job_type,
                    matched_terms=matched_terms,
                    score=score,
                )
                send_reply_options(replies)

            new_seen.add(unique_id)

    save_seen(new_seen)


if __name__ == "__main__":
    run()
