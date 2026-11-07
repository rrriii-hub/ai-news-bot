"""目覚まし（.github/workflows/ai-news-timer.yml から約1時間ごとに呼ばれる）

GitHubの定時実行は混雑すると何時間も遅れるため、
「環境の待ち時間（Wait timer）で約55分待つ → このスクリプト → 次の目覚ましをセット」をくり返し、
投稿時刻が近づいたらBotを mode=daily で起こす（Botは投稿時刻ちょうどまで待ってから投稿する）。
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.abspath(__file__))
API = os.environ.get("GITHUB_API_URL", "https://api.github.com")
REPO = os.environ.get("GITHUB_REPOSITORY", "")
REF = os.environ.get("GITHUB_REF_NAME", "main")
RUN_ID = os.environ.get("GITHUB_RUN_ID", "")
BOT_WORKFLOW = "daily-ai-news.yml"
TIMER_WORKFLOW = "ai-news-timer.yml"
MIN_WAIT_MINUTES = 45     # これより早く動いた＝待ち時間が設定されていない（すぐ次を起動すると止まらなくなる）
WAKE_BEFORE_MINUTES = 65  # 投稿時刻のこの分数前から、Botを起こす（Botはそこから投稿時刻まで待つ）
WAKE_AFTER_MINUTES = 60   # 投稿時刻を過ぎても、この分数以内でまだ投稿していなければBotを起こす


def api(method, path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={
        "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


def load_json(name, default):
    try:
        with open(os.path.join(ROOT, name), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def minutes_to_post(config, now):
    """前後12時間以内でいちばん近い投稿時刻まで何分か（過ぎていればマイナス）と、その日付"""
    hh, mm = map(int, config.get("post_time_jst", "15:00").split(":"))
    local = now.astimezone(JST)
    target = local.replace(hour=hh, minute=mm, second=0, microsecond=0)
    diff = (target - local).total_seconds()
    if diff < -12 * 3600:
        target += timedelta(days=1)
    elif diff > 12 * 3600:
        target -= timedelta(days=1)
    return (target - local).total_seconds() / 60, target.date()


def set_next_timer():
    """待機中の目覚ましがなければ次をセットする。二重になっていたら古い1つだけ残す"""
    runs = api("GET", f"/repos/{REPO}/actions/workflows/{TIMER_WORKFLOW}/runs?per_page=30")["workflow_runs"]
    others = sorted((r for r in runs if r["status"] != "completed" and str(r["id"]) != RUN_ID),
                    key=lambda r: r["created_at"])
    if not others:
        api("POST", f"/repos/{REPO}/actions/workflows/{TIMER_WORKFLOW}/dispatches", {"ref": REF})
        print("[info] 次の目覚ましをセットしました")
        return
    for extra in others[1:]:
        if extra["status"] != "in_progress":
            api("POST", f"/repos/{REPO}/actions/runs/{extra['id']}/cancel")
            print(f"[info] 二重になっていた目覚まし（{extra['id']}）を止めました")
    print("[info] 次の目覚ましはセット済みです")


def wake_bot_if_needed(now):
    config = load_json("config.json", {})
    history = load_json("posted.json", {})
    minutes, day = minutes_to_post(config, now)
    if history.get("last_post_date") == day.isoformat():
        print(f"[info] {day:%m/%d} の分は投稿済みです")
    elif -WAKE_AFTER_MINUTES <= minutes <= WAKE_BEFORE_MINUTES:
        api("POST", f"/repos/{REPO}/actions/workflows/{BOT_WORKFLOW}/dispatches",
            {"ref": REF, "inputs": {"mode": "daily"}})
        print(f"[info] 投稿時刻まであと {minutes:.0f} 分なので、Botを起こしました")
    else:
        print(f"[info] 投稿時刻まであと {minutes:.0f} 分（まだ起こしません）")


def main():
    now = datetime.now(timezone.utc)
    run = api("GET", f"/repos/{REPO}/actions/runs/{RUN_ID}")
    created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
    waited = (now - created).total_seconds() / 60
    if waited < MIN_WAIT_MINUTES:
        print(f"[info] 待ち時間が {waited:.0f} 分しかありませんでした。Settings → Environments の「news-timer」に"
              "Wait timer（55分）が設定されていないので、目覚ましは使いません（README の⑥）")
        return

    failed = False
    for step in (set_next_timer, lambda: wake_bot_if_needed(now)):  # 片方が失敗しても、もう片方はやる
        try:
            step()
        except Exception as e:
            failed = True
            print(f"[error] {e}", file=sys.stderr)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
