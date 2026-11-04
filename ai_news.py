"""毎日のAIニュースをDiscordに投稿するスクリプト（Python標準ライブラリのみ・無料）

環境変数:
  DISCORD_WEBHOOK_URL  投稿先チャンネルのWebhook URL（必須。未設定なら画面に表示するだけ）
  DRY_RUN=1            投稿せずに結果を表示するだけ（お試し用）
"""
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

JST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(ROOT, "config.json")
HISTORY_PATH = os.path.join(ROOT, "posted.json")
HISTORY_LIMIT = 1000
FETCH_UA = "Mozilla/5.0 (compatible; ai-news-discord-bot/1.0)"
DISCORD_UA = "DiscordBot (https://github.com, 1.0)"


# ---------- ユーティリティ ----------
def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def local(tag):
    return tag.rsplit("}", 1)[-1]


def child(el, *names):
    for c in el:
        if local(c.tag) in names:
            return c
    return None


def child_text(el, *names):
    c = child(el, *names)
    return (c.text or "").strip() if c is not None else ""


def strip_html(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_title(t):
    return re.sub(r"[\s\W_]+", "", t.lower())


def parse_date(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def truncate(s, n):
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------- ニュース取得 ----------
def feed_url(feed):
    if feed.get("google_news"):
        q = urllib.parse.quote(f'{feed["google_news"]} when:1d')
        return f"https://news.google.com/rss/search?q={q}&hl=ja&gl=JP&ceid=JP:ja"
    return feed["url"]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": FETCH_UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def parse_feed(data, feed_name):
    root = ET.fromstring(data)
    items = []
    for el in root.iter():
        if local(el.tag) not in ("item", "entry"):
            continue
        title = strip_html(child_text(el, "title"))
        link_el = child(el, "link")
        link = ""
        if link_el is not None:
            link = (link_el.get("href") or link_el.text or "").strip()
        if not title or not link:
            continue

        source = feed_name
        src_el = child(el, "source")
        if src_el is not None and (src_el.text or "").strip():
            source = src_el.text.strip()
            # Googleニュースはタイトル末尾に「 - 媒体名」が付くので外す
            suffix = " - " + source
            if title.endswith(suffix):
                title = title[: -len(suffix)]

        desc = strip_html(child_text(el, "description", "summary", "content"))
        if not desc or normalize_title(desc).startswith(normalize_title(title)[:20]):
            desc = ""  # 中身のない説明文は使わない

        date = parse_date(child_text(el, "pubDate", "published", "updated", "date"))
        items.append({"title": title, "url": link, "source": source,
                      "desc": desc, "date": date, "feed": feed_name})
    return items


def collect(config, history):
    now = datetime.now(timezone.utc)
    max_age = timedelta(hours=config.get("max_age_hours", 36))
    seen_urls = set(history.get("urls", []))
    seen_titles = set(history.get("titles", []))

    per_feed = []
    for feed in config["feeds"]:
        try:
            items = parse_feed(fetch(feed_url(feed)), feed["name"])
        except Exception as e:  # 1つのサイトが落ちても他は続ける
            print(f"[warn] {feed['name']} の取得に失敗: {e}", file=sys.stderr)
            items = []
        exclude = [w.lower() for w in config.get("exclude_words", [])]
        fresh = [i for i in items
                 if len(i["title"]) >= 12  # 「お知らせ」などの短すぎる見出しを除外
                 and (i["date"] is None or now - i["date"] <= max_age)
                 and i["url"] not in seen_urls
                 and normalize_title(i["title"]) not in seen_titles
                 and not any(w in (i["title"] + " " + i["source"]).lower() for w in exclude)]
        # Googleニュースは「注目度順」で返ってくるのでそのまま、それ以外は新しい順
        if not feed.get("google_news"):
            fresh.sort(key=lambda i: i["date"] or datetime.min.replace(tzinfo=timezone.utc),
                       reverse=True)
        print(f"[info] {feed['name']}: {len(items)}件取得 / 新着 {len(fresh)}件")
        per_feed.append(fresh)

    # 各ソースから順番に1件ずつ取り、偏らないように選ぶ
    picked, picked_titles = [], set()
    count = config.get("count", 5)
    while len(picked) < count and any(per_feed):
        for queue in per_feed:
            while queue:
                item = queue.pop(0)
                key = normalize_title(item["title"])
                if key in picked_titles:
                    continue
                picked.append(item)
                picked_titles.add(key)
                break
            if len(picked) >= count:
                break
    return picked


# ---------- Discord投稿 ----------
def build_payload(config, items, today):
    embeds = []
    for n, i in enumerate(items, 1):
        e = {
            "title": truncate(f"{n}. {i['title']}", 256),
            "url": i["url"],
            "color": config.get("color", 5793266),
            "footer": {"text": truncate(i["source"], 100)},
        }
        if i["desc"]:
            e["description"] = truncate(i["desc"], 200)
        if i["date"]:
            e["timestamp"] = i["date"].astimezone(timezone.utc).isoformat()
        embeds.append(e)
    payload = {
        "username": config.get("bot_name", "AIニュース"),
        "content": config.get("header", "📰 今日のAIニュース（{date}）").format(
            date=today.strftime("%Y/%m/%d")),
        "embeds": embeds,
        "allowed_mentions": {"parse": []},
    }
    if config.get("avatar_url"):
        payload["avatar_url"] = config["avatar_url"]
    return payload


def post_discord(webhook, payload):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(webhook, data=body, method="POST", headers={
        "Content-Type": "application/json", "User-Agent": DISCORD_UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20):
                return
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:  # レート制限なら待って再送
                time.sleep(5)
                continue
            raise RuntimeError(f"Discordへの投稿に失敗 ({e.code}): {e.read()[:300]!r}")


# ---------- メイン ----------
def wait_for_post_time(config):
    """定時実行のときだけ、指定時刻（日本時間）まで待つ。GitHubの起動遅れ対策で少し早めに起動している"""
    hh, mm = map(int, config.get("post_time_jst", "15:00").split(":"))
    now = datetime.now(JST)
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    wait = (target - now).total_seconds()
    if 0 < wait <= 40 * 60:
        print(f"[info] {target:%H:%M} まで {int(wait)} 秒待ちます")
        time.sleep(wait)


def main():
    config = load_json(CONFIG_PATH, None)
    if not config:
        sys.exit("config.json が読めません")
    history = load_json(HISTORY_PATH, {"last_post_date": "", "urls": [], "titles": []})

    scheduled = os.environ.get("GITHUB_EVENT_NAME") == "schedule"
    today = datetime.now(JST).date()
    if scheduled and history.get("last_post_date") == today.isoformat():
        print("[info] 今日はもう投稿済みなのでスキップします")
        return
    if scheduled:
        wait_for_post_time(config)

    items = collect(config, history)
    if not items:
        print("[info] 新しいニュースがなかったので投稿しません")
        return

    payload = build_payload(config, items, today)
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if os.environ.get("DRY_RUN") == "1" or not webhook:
        print("[dry-run] 以下の内容を投稿します（実際には送っていません）")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    post_discord(webhook, payload)
    print(f"[info] {len(items)}件を投稿しました")

    history["urls"] = (history.get("urls", []) + [i["url"] for i in items])[-HISTORY_LIMIT:]
    history["titles"] = (history.get("titles", []) +
                         [normalize_title(i["title"]) for i in items])[-HISTORY_LIMIT:]
    if scheduled:
        history["last_post_date"] = today.isoformat()
    save_json(HISTORY_PATH, history)


if __name__ == "__main__":
    main()
