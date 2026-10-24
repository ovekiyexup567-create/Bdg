# BDG Period Analyzer (starter)

This is a Telegram bot starter for recording and analyzing published BDG results.
It does **not** log into BDG, automate a gambling account, place bets, or guarantee
future outcomes. Historical patterns are descriptive, not proof that the next
result can be predicted.

## Commands

- `/start` — instructions
- `/add PERIOD NUMBER` — store one published result, e.g. `/add 202610241000010471 7`
- `/history` — latest 10 records
- `/stats` — statistics for the latest 50 recorded periods
- `/report` — send the current report

## Run locally

1. Install Python 3.11 or newer.
2. Run `pip install -r requirements.txt`.
3. Set environment variable `TELEGRAM_BOT_TOKEN` to a token from BotFather.
4. Optional: set `REPORT_CHAT_ID` to the chat that should receive a summary every 60 seconds.
5. Run `python bot.py`.

## Deploy on a cloud worker

Create a Python worker/service and use the start command:

`python bot.py`

Add environment variables in the hosting dashboard:
- `TELEGRAM_BOT_TOKEN` (required)
- `REPORT_CHAT_ID` (optional)
- `BDG_DB_PATH` (optional; default `bdg_results.sqlite3`)

Use a persistent disk/volume if the hosting provider's filesystem is ephemeral, otherwise SQLite history may be lost on redeploy. The host must support a continuously running worker. If it only supports short-lived serverless functions, use a compatible always-on worker instead.

## Important limitations

- Results are entered with `/add`; live BDG collection is not implemented because the website's authorized data interface has not been established.
- The color mapping is inferred from the screenshots and should be checked against the game's own rules.
- The 60-second job posts a statistical summary, not a guaranteed next-result prediction.
- Do not put BDG login passwords, OTPs, or account credentials into Telegram, source files, or environment logs.
