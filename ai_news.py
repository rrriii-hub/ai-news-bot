"""毎日のニュース（AI・政治・世界情勢など）をDiscordの各チャンネルに投稿するスクリプト（Python標準ライブラリのみ・無料）

環境変数:
  DISCORD_WEBHOOK_URL  投稿先チャンネルのWebhook URL（チャンネルごとの名前は config.json の webhook_secret。
                       GitHub Actionsでは未登録のチャンネルは飛ばす。手元で未設定なら表示だけ）
  GEMINI_API_KEY       「今日のまとめ」の文章をGoogleのAI（Gemini API・無料枠）で作るため。未登録ならニュースだけ投稿
  RUN_MODE=check       投稿せずに、投稿先チャンネルと投稿する中身（ニュース・まとめ）を確認する
  RUN_MODE=daily       毎日の定時投稿と同じ動き（1日1回だけ・投稿時刻まで待つ）。手動での出し直しなどに
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
WEBHOOK_RE = re.compile(
    r"^https://(?:(?:ptb|canary)\.)?discord(?:app)?\.com/api(?:/v\d+)?/webhooks/\d+/[\w-]+/?(?:\?.*)?$")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
SUMMARY_TITLE = "📝 **今日のまとめ**"
SUMMARY_PROMPT = """あなたはニュースの編集者です。渡されたニュースの見出しと概要だけをもとに、今日の{topic}の動きを日本語で軽くまとめてください。
・2〜4文、全体で200字前後の自然な文章（です・ます調）
・箇条書き、見出し、URL、絵文字は使わない
・渡された内容に書かれていないことは書かない（推測や誇張をしない）
・特定の政党・国・人物に肩入れせず、中立的に書く"""


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


def title_grams(t):
    n = normalize_title(t)
    return {n[i:i + 2] for i in range(len(n) - 1)}


def is_similar(a, b, threshold=0.45):
    """見出しの文字の並びがどれだけ重なっているか（同じ話題を別サイトが報じた記事をまとめるため）"""
    return len(a & b) / max(1, min(len(a), len(b))) >= threshold


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
        # Googleニュースは「注目度順」で返ってくるのでそのまま（keep_order も同じ）、それ以外は新しい順
        if not feed.get("google_news") and not feed.get("keep_order"):
            fresh.sort(key=lambda i: i["date"] or datetime.min.replace(tzinfo=timezone.utc),
                       reverse=True)
        print(f"[info] {feed['name']}: {len(items)}件取得 / 新着 {len(fresh)}件")
        per_feed.append(fresh)

    # 各ソースから順番に1件ずつ取り、偏らないように選ぶ
    # 同じ話題の記事（過去に流したものも含む）は1件だけにする
    seen = [title_grams(t) for t in history.get("titles", [])]
    picked = []
    count = config.get("count", 5)
    while len(picked) < count and any(per_feed):
        for queue in per_feed:
            while queue:
                item = queue.pop(0)
                grams = title_grams(item["title"])
                duplicate = any(is_similar(grams, g) for g in seen)
                seen.append(grams)
                if duplicate:
                    continue
                picked.append(item)
                break
            if len(picked) >= count:
                break
    return picked


# ---------- 今日のまとめ ----------
def make_summary(config, items):
    """GoogleのAI（Gemini API の無料枠）で、選んだニュースを短い文章にまとめる。
    作れないとき（GEMINI_API_KEY が未登録・AIの混雑など）は None を返し、ニュースだけ投稿する"""
    if not config.get("summary", True) or not items:
        return None
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("[info] GEMINI_API_KEY が登録されていないので、まとめの文章は付けません（README の⑤）")
        return None
    lines = []
    for n, i in enumerate(items, 1):
        lines.append(f"{n}. {i['title']}（{i['source']}）")
        if i["desc"]:
            lines.append(f"   {truncate(i['desc'], 200)}")
    topic = config.get("summary_topic", "AI業界")
    body = {
        "systemInstruction": {"parts": [{"text": SUMMARY_PROMPT.format(topic=topic)}]},
        "contents": [{"role": "user", "parts": [{"text": f"今日の{topic}のニュース:\n" + "\n".join(lines)}]}],
    }
    model = urllib.parse.quote(config.get("summary_model", "gemini-3.5-flash-lite"), safe="-._")
    req = urllib.request.Request(GEMINI_URL.format(model=model), data=json.dumps(body).encode("utf-8"),
                                 headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        print(f"[warn] まとめの文章を作れませんでした ({e.code}): {e.read()[:300]!r}", file=sys.stderr)
        return None
    except Exception as e:  # まとめが作れなくてもニュースは投稿する
        print(f"[warn] まとめの文章を作れませんでした: {e}", file=sys.stderr)
        return None
    try:  # 考え中のメモ（thought）は除いて、本文だけをつなげる
        parts = res["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    except (KeyError, IndexError, TypeError, AttributeError):
        text = ""
    if not text:
        print(f"[warn] まとめの文章が空でした: {json.dumps(res, ensure_ascii=False)[:300]}", file=sys.stderr)
        return None
    return truncate(text, 1500)


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


def build_summary_payload(config, summary):
    payload = {
        "username": config.get("bot_name", "AIニュース"),
        "content": f"{SUMMARY_TITLE}\n{summary}",
        "allowed_mentions": {"parse": []},
    }
    if config.get("avatar_url"):
        payload["avatar_url"] = config["avatar_url"]
    return payload


def print_preview(payload, summary):
    print(payload["content"])
    for e in payload["embeds"]:
        print(f"  {e['title']}（{e['footer']['text']}）")
    if summary:
        print(f"\n{SUMMARY_TITLE}\n{summary}")


class DiscordError(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """転送（リダイレクト）は失敗扱いにする。招待リンクなどを登録したときに「成功」と誤判定しないため"""
    def redirect_request(self, *args, **kwargs):
        return None


DISCORD = urllib.request.build_opener(_NoRedirect)


def discord_request(url, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET", headers={
        "Content-Type": "application/json", "User-Agent": DISCORD_UA})
    for attempt in range(3):
        try:
            with DISCORD.open(req, timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:  # レート制限なら待って再送
                time.sleep(5)
                continue
            if e.code in (401, 404):
                raise DiscordError("[error] Webhookが見つかりません。Discord側で削除されたか、URLが間違っています。"
                                   "README の②③をやり直してください。")
            raise DiscordError(f"[error] Discordへの接続に失敗 ({e.code}): {e.read()[:300]!r}")


def check_webhook(webhook, secret="DISCORD_WEBHOOK_URL"):
    """Webhookの名前と投稿先チャンネルをログに出す（投稿はしない）"""
    if not WEBHOOK_RE.match(webhook):
        raise DiscordError(f"[error] {secret} がDiscordのWebhook URLになっていません。\n"
                           "招待リンク（discord.gg/...）やチャンネルのURLではなく、\n"
                           "サーバー設定 → 連携サービス → ウェブフック →「ウェブフックURLをコピー」で取った\n"
                           "https://discord.com/api/webhooks/ で始まるURLを登録し直してください（README の②③）。")
    info = discord_request(webhook.split("?")[0])
    print(f"[info] Webhook名: {info.get('name')} / 投稿先チャンネル: "
          f"https://discord.com/channels/{info.get('guild_id')}/{info.get('channel_id')}")
    return info


def post_discord(webhook, payload):
    """?wait=true を付けて、Discordに「実際に投稿したメッセージ」を返してもらう"""
    sep = "&" if "?" in webhook else "?"
    msg = discord_request(f"{webhook}{sep}wait=true", payload)
    if not isinstance(msg, dict) or not msg.get("id"):
        raise DiscordError("[error] Discordから投稿結果が返ってきませんでした")
    return msg


# ---------- メイン ----------
def nearest_post_time(config, now):
    """前後12時間以内でいちばん近い投稿時刻（日本時間）。
    起動が遅れて日付をまたいでも、何日の分の投稿かを取り違えないように"""
    hh, mm = map(int, config.get("post_time_jst", "15:00").split(":"))
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    diff = (target - now).total_seconds()
    if diff < -12 * 3600:
        target += timedelta(days=1)
    elif diff > 12 * 3600:
        target -= timedelta(days=1)
    return target


def channel_list(config):
    """投稿先チャンネルの一覧（config.json の channels。なければ従来どおりAIの1チャンネル）"""
    if config.get("channels"):
        return config["channels"]
    return [{"name": "AI", "webhook_secret": "DISCORD_WEBHOOK_URL"}]


def load_history():
    """投稿済みの記録。以前の形式（AIチャンネルだけ）なら、AIチャンネルの記録として引き継ぐ"""
    h = load_json(HISTORY_PATH, {})
    if "channels" not in h:
        old = {"last_post_date": h.get("last_post_date", ""),
               "urls": h.get("urls", []), "titles": h.get("titles", [])}
        h = {"last_post_date": old["last_post_date"],
             "channels": {"AI": old} if (old["urls"] or old["last_post_date"]) else {}}
    return h


def main():
    config = load_json(CONFIG_PATH, None)
    if not config:
        sys.exit("config.json が読めません")
    history = load_history()

    mode = os.environ.get("RUN_MODE", "")
    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    force_dry = os.environ.get("DRY_RUN") == "1"
    check_only = mode == "check"

    # 毎日の定時投稿（GitHubの定時実行、または mode=daily）は1日1回だけ。
    # 投稿時刻の少し前に起動したら、ニュースとまとめを用意してから時刻ちょうどまで待って投稿する
    daily = os.environ.get("GITHUB_EVENT_NAME") == "schedule" or mode == "daily"
    now = datetime.now(JST)
    post_day = now.date()
    target = None
    if daily:  # 投稿済みかどうかはチャンネルごとに判断する（あとから足したチャンネルも、その日のうちに出せる）
        target = nearest_post_time(config, now)
        post_day = target.date()
        if (target - now).total_seconds() > 65 * 60:
            print(f"[info] 投稿時刻（{target:%m/%d %H:%M}）の65分以上前なので、何もせずに終わります")
            return

    errors = []
    ready = []        # 投稿の準備ができたチャンネル
    changed = False   # 投稿済みの記録を書き換えたか
    has_webhook = False
    for ch in channel_list(config):
        name = ch.get("name", "AI")
        conf = {**config, **ch}  # チャンネルごとの設定を優先する
        hist = history["channels"].setdefault(name, {"last_post_date": "", "urls": [], "titles": []})
        secret = ch.get("webhook_secret", "DISCORD_WEBHOOK_URL")
        webhook = os.environ.get(secret, "").strip()
        has_webhook = has_webhook or bool(webhook)
        if daily and hist.get("last_post_date") == post_day.isoformat():
            print(f"[info] [{name}] {post_day:%m/%d} の分は投稿済みです")
            continue
        dry_run = force_dry or (not webhook and not in_actions)
        if not dry_run and not webhook:
            print(f"[info] [{name}] {secret} が登録されていないので、このチャンネルは飛ばします（README の③）")
            continue
        info = {}
        if not dry_run:
            try:
                info = check_webhook(webhook, secret)
            except DiscordError as e:
                errors.append(f"[{name}] {e}")
                continue

        items = collect(conf, hist)
        if not items:
            print(f"[info] [{name}] 新しいニュースがなかったので投稿しません")
            if daily and not (dry_run or check_only):
                hist["last_post_date"] = post_day.isoformat()
                changed = True
            continue
        payload = build_payload(conf, items, post_day)
        summary = make_summary(conf, items)
        if dry_run or check_only:
            print(f"[dry-run] [{name}] 以下の内容を投稿します（実際には送っていません）" if dry_run else
                  f"[check] [{name}] 接続チェックOK。以下は確認用の表示で、投稿はしていません")
            print_preview(payload, summary)
            continue
        ready.append((name, conf, hist, webhook, info, items, payload, summary))

    if in_actions and not force_dry and not has_webhook:
        sys.exit("[error] DISCORD_WEBHOOK_URL が登録されていません（README の③）")

    if ready and target:
        wait = (target - datetime.now(JST)).total_seconds()
        if wait > 0:
            print(f"[info] {target:%H:%M} まで {int(wait)} 秒待ちます")
            time.sleep(wait)

    for name, conf, hist, webhook, info, items, payload, summary in ready:
        try:
            msg = post_discord(webhook, payload)
        except DiscordError as e:
            errors.append(f"[{name}] {e}")
            continue
        print(f"[info] [{name}] {len(items)}件を投稿しました → https://discord.com/channels/"
              f"{info.get('guild_id')}/{msg.get('channel_id')}/{msg['id']}")
        hist["urls"] = (hist.get("urls", []) + [i["url"] for i in items])[-HISTORY_LIMIT:]
        hist["titles"] = (hist.get("titles", []) +
                          [normalize_title(i["title"]) for i in items])[-HISTORY_LIMIT:]
        if daily:
            hist["last_post_date"] = post_day.isoformat()
        changed = True
        save_json(HISTORY_PATH, history)  # 1チャンネルずつ記録して、二重投稿を防ぐ
        if summary:
            try:
                post_discord(webhook, build_summary_payload(conf, summary))
                print(f"[info] [{name}] 今日のまとめを投稿しました")
            except Exception as e:  # まとめが送れなくても、ニュースの投稿と記録は済んでいる
                print(f"[warn] [{name}] まとめの投稿に失敗しました: {e}", file=sys.stderr)

    if daily and not errors and not (force_dry or check_only) and (in_actions or has_webhook):
        history["last_post_date"] = post_day.isoformat()  # 全チャンネル済み（失敗があれば次の起動でやり直す）
        changed = True
    if changed:
        save_json(HISTORY_PATH, history)
    if errors:
        sys.exit("\n".join(errors))


if __name__ == "__main__":
    main()
