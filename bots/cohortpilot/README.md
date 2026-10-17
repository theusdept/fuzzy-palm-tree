# CohortPilot — Telegram group check-ins

A privacy-first learning cohort bot for educators, coaches and community operators. Free beta only; checkout is disabled.

## Commands

Group owner/admin: `/cohort NAME`, `/task DESCRIPTION`, `/reminders on|off`, `/closecohort confirm`.

Members: `/join`, `/done [TASK_ID]`, `/progress [TASK_ID]`, `/leave`, `/privacy`.

Private chat: `/start`, `/myid`, `/mydata`, `/delete_me confirm`, `/privacy`, `/terms`.

## Deployment

Set `BOT_TOKEN` only as a Railway secret. Set `DB_PATH=/data/cohortpilot.db` and `PORT=8080`; attach a persistent volume at `/data`. Deploy one polling replica, because two pollers sharing a token will conflict. Docker build context is `bots/cohortpilot`. `/health` is process health, `/ready` requires successful Telegram polling. Do not remove an existing webhook automatically; review it first.

**Status:** A locally tested implementation and 11 unit tests exist in the archived source package. The service remains staged, with no BotFather token, and therefore must not be represented as a running bot. Do not deploy Dockerfile without `app.py` and tests in the same branch.

## Data handling

Users opt in. Numeric Telegram user IDs and check-ins are stored in SQLite. `/leave` and private `/delete_me confirm` erase member participation; old tasks expire after 90 days. No payment collection, wagering, mass DMs, or unsanctioned group scraping.
