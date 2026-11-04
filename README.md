# 📰 AIニュース Discord Bot（無料・サーバー不要）

毎日 **15:00（日本時間）** に、主要なAIニュースを **5件** Discordチャンネルへ自動投稿します。

- 💰 **完全無料**：GitHub Actions（無料枠）＋ Discord Webhook だけで動きます
- 🖥️ **PCの電源オフでもOK**：GitHubのサーバーが毎日実行します
- 🔁 **重複なし**：一度流したニュースは記録して、次の日以降は流しません
- ⚙️ **カスタマイズ簡単**：`config.json` を書き換えるだけ（時刻・件数・ニュース元）

ニュース元（初期設定）：ITmedia AI+ ／ Googleニュース（生成AI・ChatGPT・Gemini・Claude など）／ Googleニュース（OpenAI・Anthropic・Google DeepMind など）

---

## 🚀 導入手順（10分くらい）

### ① GitHub にこのBotをコピーする

1. [GitHub](https://github.com/) のアカウントを作る（無料）
2. 配布元のページで緑の **「Use this template」→「Create a new repository」** を押す
   - 名前は何でもOK（例：`ai-news-bot`）
   - **Public（公開）を推奨**（Publicなら実行時間が無制限で無料。Privateでも月2,000分の無料枠内で収まります）
3. 「Create repository」を押す

> zipで受け取った場合：GitHubで新しいリポジトリを作り、「Add file → Upload files」で中身をフォルダごとドラッグ＆ドロップしてください（`.github` フォルダも忘れずに）。

### ② Discord で Webhook URL を作る

1. 投稿したいサーバーで **サーバー設定 → 連携サービス → ウェブフック** を開く
2. **「新しいウェブフック」** を押す
3. 名前（例：AIニュース）と **投稿先チャンネル** を選ぶ
4. **「ウェブフックURLをコピー」** を押す

> ⚠️ このURLを知っている人は誰でもそのチャンネルに投稿できます。**人に見せたり、ファイルに直接書いたりしないでください。**（③の「Secrets」に入れれば安全です）
> ※ サーバーの「ウェブフックの管理」権限が必要です。

### ③ GitHub に Webhook URL を登録する

1. 自分のリポジトリで **Settings → Secrets and variables → Actions** を開く
2. **「New repository secret」** を押す
3. 次のように入力して「Add secret」
   - **Name**：`DISCORD_WEBHOOK_URL`
   - **Secret**：②でコピーしたURL

### ④ 動作テスト

1. リポジトリ上部の **Actions** タブを開く（「ワークフローを有効にしますか？」と出たら有効にする）
2. 左の **「Daily AI News」** → 右の **「Run workflow」** → 緑の「Run workflow」
3. 1分ほどでDiscordにニュースが届けば成功 🎉

あとは毎日15:00に自動で投稿されます。

---

## ⚙️ カスタマイズ（`config.json`）

GitHub上で `config.json` を開き、✏️（鉛筆）ボタンで編集 →「Commit changes」で保存できます。

| 項目 | 意味 | 初期値 |
|---|---|---|
| `post_time_jst` | 投稿時刻（日本時間） | `"15:00"` |
| `count` | 1日に流す件数（最大10） | `5` |
| `max_age_hours` | 何時間以内のニュースを対象にするか | `36` |
| `bot_name` | Discordに表示される名前 | `"AIニュース速報"` |
| `avatar_url` | アイコン画像のURL（空ならWebhookのアイコン） | `""` |
| `header` | 最初の一言（`{date}` が日付に置き換わる） | `📰 **今日の主要AIニュース**（{date}）` |
| `exclude_words` | この言葉を含むニュースは除外 | セミナー・PR など |
| `feeds` | ニュース元の一覧（上にあるほど優先） | 3つ |

### ニュース元を増やす

`feeds` に追加します。RSSのURLを書く方法と、Googleニュースの検索キーワードを書く方法があります。

```json
{ "name": "好きな名前", "url": "https://example.com/rss.xml" },
{ "name": "Googleニュース（画像生成AI）", "google_news": "画像生成AI OR Midjourney OR \"Stable Diffusion\"" }
```

### 投稿時刻を15時以外にする

`config.json` の `post_time_jst` と、`.github/workflows/daily-ai-news.yml` の `cron` の **両方** を変えます。
`cron` は **世界標準時（日本時間 − 9時間）** で、**投稿時刻の15分前** を指定してください。

| 投稿したい時刻（日本時間） | `post_time_jst` | `cron` |
|---|---|---|
| 08:00 | `"08:00"` | `"45 22 * * *"` |
| 12:00 | `"12:00"` | `"45 2 * * *"` |
| 15:00 | `"15:00"` | `"45 5 * * *"` |
| 21:00 | `"21:00"` | `"45 11 * * *"` |

---

## ❓ よくある質問

**Q. 本当にお金はかからない？**
A. かかりません。GitHub Actions は Public リポジトリなら無料・無制限、Private でも無料枠（月2,000分）に対して月30分程度しか使いません。Discord Webhook も無料です。AIの要約APIなどの有料サービスは使っていません。

**Q. 15:00ぴったりに来ない**
A. GitHubは混雑時に起動が遅れることがあるため、14:45に起動して15:00まで待つ仕組みにしています。それでもGitHub側が大きく遅れた日は数分〜数十分遅れることがあります。

**Q. 投稿されない / Actionsが赤く失敗している**
- Actions タブで失敗した実行を開き、ログを確認してください
- `Discordへの投稿に失敗 (401/404)` → Webhook URL が間違っているか、Discord側で削除されています。③をやり直してください
- `git push` で失敗 → **Settings → Actions → General → Workflow permissions** を **「Read and write permissions」** にして保存
- 新着ニュースが0件の日は投稿しません（ログに「新しいニュースがなかった」と出ます）

**Q. 止めたい**
A. Actions タブ →「Daily AI News」→ 右上「…」→ **Disable workflow**。

**Q. 60日で止まるって聞いたけど？**
A. GitHubは60日間更新がないリポジトリの定時実行を止めますが、このBotは毎日 `posted.json`（投稿履歴）を自動更新するので止まりません。

---

## 🧪 自分のPCで試す（上級者向け）

Python 3.9以上があれば、投稿せずに中身だけ確認できます。

```bash
DRY_RUN=1 python ai_news.py
```

## 📁 ファイル構成

```
ai_news.py                         … 本体（ニュース取得＆Discord投稿）
config.json                        … 設定
posted.json                        … 投稿済みの記録（自動更新）
.github/workflows/daily-ai-news.yml … 毎日の自動実行の設定
```
