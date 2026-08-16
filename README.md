# Odyssey IMAX Showtime Monitor

Checks Forum Cinemas Vingis (Vilnius) a few times a day for new IMAX
showtimes of *The Odyssey* and pings you on Telegram the moment a new
date/time appears — so you can jump on seat selection early.

## How it works

- Runs on a schedule via **GitHub Actions** (free for public/private repos
  within generous limits) — no server needed.
- Scrapes the published schedule, remembers what it saw last time in
  `state.json` (committed back to the repo each run), and only messages
  you about genuinely **new** showtimes.
- Sends the alert via a **Telegram bot** message.

## One-time setup (~10 minutes)

### 1. Create a Telegram bot
1. Open Telegram, search for **@BotFather**, start a chat.
2. Send `/newbot`, follow the prompts (choose a name and a username ending
   in `bot`).
3. BotFather replies with a **token** like `123456789:AAbecZ...` — save it.

### 2. Get your chat ID
1. Search for your new bot in Telegram and send it any message (e.g. "hi").
2. In a browser, visit:
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   (replace `<YOUR_TOKEN>` with the token from step 1)
3. Look for `"chat":{"id":123456789, ...}` in the JSON response — that
   number is your **chat ID**.

### 3. Create a GitHub repo
1. Create a new (can be private) repo on GitHub, e.g. `odyssey-monitor`.
2. Upload these files to it, preserving the folder structure:
   ```
   odyssey-monitor/
   ├── monitor.py
   ├── requirements.txt
   ├── state.json
   ├── README.md
   └── .github/workflows/monitor.yml
   ```
   (Easiest: `git init`, `git add .`, `git commit -m "init"`, then push to
   the new GitHub repo — or just drag-and-drop the files in the GitHub web
   UI, keeping the `.github/workflows/` folder intact.)

### 4. Add your secrets
In the repo: **Settings → Secrets and variables → Actions → New repository
secret**, add two secrets:
- `TELEGRAM_BOT_TOKEN` — the token from step 1
- `TELEGRAM_CHAT_ID` — the chat ID from step 2

### 5. Test it
Go to the **Actions** tab → **Odyssey IMAX Showtime Monitor** →
**Run workflow** (this is the `workflow_dispatch` trigger, lets you fire it
manually instead of waiting for the schedule). Check the run logs — you
should see either "No new IMAX showtimes found" or a Telegram message if
new ones are already there relative to whatever's in `state.json`.

That's it — after this it runs automatically 3x/day and only messages you
when something actually changes.

## Adjusting things later

- **Check frequency**: edit the `cron:` line in
  `.github/workflows/monitor.yml`. Cron syntax is `min hour day month
  weekday`, all in UTC.
- **Different cinema/movie**: edit `MOVIE_NAME` in `monitor.py`. For a
  different cinema, the schedule URL on kinoafisha.info will have a
  different numeric ID — find it by browsing to the cinema's page there.
- **Site structure changes**: if Forum Cinemas or kinoafisha.info redesign
  their page and the parser stops finding showtimes, the `print()` output
  in the Action logs will show `Currently tracked dates: []` even though
  you know showtimes exist — that's the signal to come back and ask for
  the parser to be updated to match the new page structure.

## Important limits (read this)

- This **only alerts you** — it does not and cannot buy tickets for you.
  Seat selection and payment need a human, on purpose (this is your money
  and your seat preference).
- It relies on kinoafisha.info's schedule page as a proxy for Forum
  Cinemas' own schedule (more reliable to parse than forumcinemas.lt's
  own site). In the rare case they're out of sync, forumcinemas.lt itself
  remains the source of truth for booking.
- GitHub Actions on the free tier has usage minutes, but a script that
  runs a few times a day for a few seconds each is far under any limit.
