import os
import json
import requests
import praw
from pathlib import Path

SUBREDDITS = ["forhire", "slavelabour", "DoneDirtCheap"]

EASY_WIN_KEYWORDS = [
    "script", "bot", "automation", "automate", "scrape", "scraper",
    "python", "api", "tool", "browser automation", "simple website",
    "landing page", "fix bug", "debug", "small task", "quick task"
]

HIGH_VALUE_KEYWORDS = [
    "saas", "web app", "mobile app", "dashboard", "full stack",
    "full-stack", "ai app", "crm", "custom software", "platform",
    "booking system", "automation system", "integrate", "integration",
    "stripe", "backend", "frontend", "next.js", "react", "django"
]

NEGATIVE_KEYWORDS = [
    "nsfw", "adult", "crypto scam", "gambling"
]

TELEGRAM_TOKEN = os.getenv("8703036561:AAEJqNLFuzo7Q5j9gPXF3ZFfLTUu5bIM5q0")
CHAT_ID = os.getenv("7523982910")

SEEN_FILE = Path("seen_posts.json")


def load_seen():
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text()))
        except Exception:
            return set()
    return set()


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(list(seen), indent=2))


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "disable_web_page_preview": True
        },
        timeout=20
    )


def classify_post(text):
    lower = text.lower()

    if any(bad in lower for bad in NEGATIVE_KEYWORDS):
        return None, []

    easy_matches = [k for k in EASY_WIN_KEYWORDS if k in lower]
    high_matches = [k for k in HIGH_VALUE_KEYWORDS if k in lower]

    if high_matches:
        return "Higher Value", high_matches

    if easy_matches:
        return "Easy Win", easy_matches

    return None, []


def generate_replies(title, job_type):
    if job_type == "Higher Value":
        return [
            f"Hey — I can help build this. I work on custom tools, automations, and web apps, and this sounds like a project I could take on. What scope, budget, and timeline are you aiming for?",
            f"This looks like something I can build. If you send over the exact features you need, I can tell you quickly what’s realistic and how fast I can turn it around.",
            f"I’m interested. I build scripts, automations, and lightweight apps, so this seems in my lane. Send me the details and I’ll reply with a plan, timeline, and price."
        ]

    return [
        f"Hey — I can probably knock this out pretty quickly. I build scripts and automations, and this looks like a good fit. What’s your deadline and budget?",
        f"I can help with this. I’ve done similar small automation/script work before and can move fast. If you send the details, I’ll tell you right away if I can do it.",
        f"This looks like something I can take care of fast. If you message me the exact task, I can give you a quick turnaround estimate and price."
    ]


def format_message(subreddit, post, job_type, matched_terms, replies):
    return (
        f"🔥 New Reddit Job\n\n"
        f"Type: {job_type}\n"
        f"Subreddit: r/{subreddit}\n"
        f"Title: {post.title}\n\n"
        f"Matched terms: {', '.join(matched_terms[:6])}\n\n"
        f"Link:\n"
        f"https://reddit.com{post.permalink}\n\n"
        f"Reply option 1:\n{replies[0]}\n\n"
        f"Reply option 2:\n{replies[1]}\n\n"
        f"Reply option 3:\n{replies[2]}"
    )


def run():
    reddit = praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT", "job-finder-bot by /u/yourusername")
    )

    seen = load_seen()
    new_seen = set(seen)

    for sub in SUBREDDITS:
        posts = reddit.subreddit(sub).new(limit=20)

        for post in posts:
            if post.id in seen:
                continue

            text = f"{post.title}\n{post.selftext}"
            job_type, matched_terms = classify_post(text)

            if job_type:
                replies = generate_replies(post.title, job_type)
                message = format_message(sub, post, job_type, matched_terms, replies)
                send_telegram(message)

            new_seen.add(post.id)

    save_seen(new_seen)


if __name__ == "__main__":
    run()
