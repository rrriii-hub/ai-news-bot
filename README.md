# 📰 AIニュース Discord Bot（無料・サーバー不要）

毎日 **15:00（日本時間）** に、主要なAIニュース **10件** と、AIが書いた **「今日のまとめ」** をDiscordチャンネルへ自動投稿します。

- 💰 **完全無料**：GitHub Actions（無料枠）＋ Discord Webhook だけで動きます。まとめの文章はGoogleのAI（Gemini API）の無料枠で作ります
- 🖥️ **PCの電源オフでもOK**：GitHubのサーバーが毎日実行します
- 📝 **今日のまとめ**：ニュースのあとに、その日の動きを2〜4文の文章でまとめて投稿します（⑤でAPIキーを1つ登録するだけ）
- 🔁 **重複なし**：一度流したニュースや、同じ話題を別のサイトが報じた記事は流しません
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
2. 左の **「Daily AI News」** → 右の **「Run workflow」** を押す
3. まず **mode を `check`** にして緑の「Run workflow」→ 投稿せずに、投稿先と中身を確認できます
   - 実行結果のログ（`post` →「Post AI news to Discord」）に、**Webhook名と投稿先チャンネルのリンク**と、投稿する予定の **ニュース**（⑤を設定していれば **「今日のまとめ」** も）が出ます
4. 問題なければ **mode を `post`** にしてもう一度実行 → 1分ほどでDiscordにニュースが届けば成功 🎉

あとは毎日15:00に自動で投稿されます（GitHub側の混雑で遅れる日があります → よくある質問）。

### ⑤ 「今日のまとめ」を付ける（おすすめ・無料）

ニュースのあとに、AIがその日の動きを2〜4文でまとめた文章を付けます。GoogleのAI（Gemini API）の無料枠を使います（クレジットカードの登録は不要）。

1. [Google AI Studio の APIキーのページ](https://aistudio.google.com/apikey) をGoogleアカウントで開く
2. **「APIキーを作成」**（Create API key）を押し、表示されたキーをコピーする
   - キーの一覧で、そのキーのプロジェクトが **無料枠（Free tier）** になっていることを確認してください（お支払い情報を設定したプロジェクトだと料金がかかることがあります）
3. GitHub の **Settings → Secrets and variables → Actions → New repository secret** で、次のように登録する
   - **Name**：`GEMINI_API_KEY`
   - **Secret**：コピーしたキー
4. ④と同じ手順で **mode を `check`** にして実行し、ログに「📝 今日のまとめ」の文章が出れば完了です

> ⚠️ APIキーも人に見せないでください。無料枠では、送った内容がGoogleのサービス改善に使われることがあります（このBotが送るのは、公開されているニュースの見出しと概要だけです）。
> 登録しなくても、ニュースはこれまでどおり毎日届きます（まとめが付かないだけです）。

### ⑥ 15:00ちょうどに届ける「目覚まし」（おすすめ・無料）

GitHubの定時実行は混雑で何時間も遅れることがあるため、約1時間ごとにBotの様子を見に行く「目覚まし」を用意しています。GitHubの「待ち時間（Wait timer）」機能を使うので、追加の登録は要りません（Publicリポジトリで使えます）。

1. リポジトリの **Settings → Environments → New environment** を押す
2. Name に `news-timer` と入れて **「Configure environment」** を押す
3. **「Wait timer」** にチェックを入れて `55`（分）と入力し、**「Save protection rules」** を押す
4. **Actions →「AI News Timer」→「Run workflow」** を1回押す（あとは自動でくり返します）

- 投稿時刻の約1時間前になると目覚ましがBotを起こし、Botが15:00ちょうどまで待ってから投稿します
- Actions の実行履歴が1日24回ほど増えます（待っている間はGitHubの実行時間を使いません）
- 目覚ましが止まっても、6時間ごとに自動で動かし直します。設定しなければ目覚ましは何もしません

---

## ⚙️ カスタマイズ（`config.json`）

GitHub上で `config.json` を開き、✏️（鉛筆）ボタンで編集 →「Commit changes」で保存できます。

| 項目 | 意味 | 初期値 |
|---|---|---|
| `post_time_jst` | 投稿時刻（日本時間） | `"15:00"` |
| `count` | 1日に流す件数（最大10） | `10` |
| `summary` | 最後に「今日のまとめ」を付けるか（`true` / `false`） | `true` |
| `summary_model` | まとめを書くAI（Gemini のモデル名） | `"gemini-3.5-flash-lite"` |
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

`config.json` の `post_time_jst` と、`.github/workflows/daily-ai-news.yml` の `cron`（3行）を **両方** 変えます。
`cron` は **世界標準時（日本時間 − 9時間）** です。1行目が本番（投稿時刻の15分前に起動）、2・3行目は遅れたとき用の予備です。⑥の目覚ましは `post_time_jst` に合わせて自動で動くので、変更は要りません。

| 投稿したい時刻（日本時間） | `post_time_jst` | `cron`（上から3行） |
|---|---|---|
| 08:00 | `"08:00"` | `"45 22 * * *"` ／ `"17 0 * * *"` ／ `"47 2 * * *"` |
| 12:00 | `"12:00"` | `"45 2 * * *"` ／ `"17 4 * * *"` ／ `"47 6 * * *"` |
| 15:00 | `"15:00"` | `"45 5 * * *"` ／ `"17 7 * * *"` ／ `"47 9 * * *"` |
| 21:00 | `"21:00"` | `"45 11 * * *"` ／ `"17 13 * * *"` ／ `"47 15 * * *"` |

---

## ❓ よくある質問

**Q. 本当にお金はかからない？**
A. かかりません。GitHub Actions は Public リポジトリなら無料・無制限、Private でも無料枠（月2,000分）に対して月30分程度しか使いません。「今日のまとめ」はGoogleのAI（Gemini API）の無料枠を1日1回使うだけなので、料金はかかりません（⑤のとおり、無料枠のプロジェクトで作ったキーを使ってください）。Discord Webhook も無料です。

**Q. 15:00ぴったりに来ない / 来ない日がある**
A. GitHubの定時実行は、混雑すると遅れたり実行されなかったりします（2026年10月ごろから、数時間遅れる例が多く報告されています）。このBotは14:45に起動して15:00まで待つ仕組みです。遅れて起動した場合は、その時点ですぐ投稿します。予備として16:17と18:47にも起動します（その日の分が投稿済みなら何もしません）。
- **⑥の「目覚まし」を設定すると、ほぼ15:00ちょうどに届くようになります**
- 今日の分を急いで出したいとき：Actions →「Daily AI News」→「Run workflow」で **mode を `daily`** にして実行します。その日にまだ投稿していなければすぐ投稿し、あとで定時実行が遅れて動いても二重には投稿しません
- 時間どおりに届けたい場合（上級者向け）：外部のタイマーサービス（cron-job.org など）から、GitHubの workflow_dispatch API で `mode: daily` を起動する方法もあります

**Q. 「今日のまとめ」が付かない日がある**
A. ⑤の `GEMINI_API_KEY` を登録していないと、まとめは付きません。登録していても、AIが混雑していたり無料枠の上限を超えたりした日は、ニュースだけを投稿します（ログに `[warn] まとめの文章を作れませんでした` と出ます）。まとめが要らない場合は `config.json` の `summary` を `false` にしてください。

**Q. 投稿されない / Actionsが赤く失敗している**
- Actions タブで失敗した実行を開き、ログを確認してください
- `Webhook URLになっていません` → 招待リンクなど別のURLを登録しています。②③をやり直してください
- `Webhookが見つかりません` → Webhook URL が間違っているか、Discord側で削除されています。②③をやり直してください
- `git push` で失敗 → **Settings → Actions → General → Workflow permissions** を **「Read and write permissions」** にして保存
- 新着ニュースが0件の日は投稿しません（ログに「新しいニュースがなかった」と出ます）

**Q. 成功したのに、見ているチャンネルに届かない**
- ログの「投稿先チャンネル」のリンクを開くと、実際に投稿されたチャンネルに飛べます
- ウェブフック作成時に投稿先チャンネルを選び忘れると、別のチャンネルに投稿されます。Discord の **サーバー設定 → 連携サービス → ウェブフック** でそのウェブフックの「チャンネル」を変えて保存してください（URLは変わらないので GitHub 側の作業は不要です）

**Q. 止めたい**
A. Actions タブ →「Daily AI News」→ 右上「…」→ **Disable workflow**。

**Q. 60日で止まるって聞いたけど？**
A. GitHubは60日間更新がないリポジトリの定時実行を止めますが、このBotは毎日 `posted.json`（投稿履歴）を自動更新するので止まりません。

---

## 🧪 自分のPCで試す（上級者向け）

Python 3.9以上があれば、投稿せずに中身だけ確認できます（環境変数 `GEMINI_API_KEY` を設定すると「今日のまとめ」も確認できます）。

```bash
DRY_RUN=1 python ai_news.py
```

## 📁 ファイル構成

```
ai_news.py                          … 本体（ニュース取得・まとめ作成・Discord投稿）
timer_hop.py                        … 目覚まし（⑥）
config.json                         … 設定
posted.json                         … 投稿済みの記録（自動更新）
.github/workflows/daily-ai-news.yml … 毎日の自動実行の設定
.github/workflows/ai-news-timer.yml … 目覚まし（⑥）の設定
```
