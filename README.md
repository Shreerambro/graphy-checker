# 🔥 Graphy Universal Checker Bot

A highly optimized Telegram Bot to check Accounts for ANY Graphy or Spayee based ecosystem dynamically via a single Base URL endpoint. Features Zero cross-account pollution and fully utilizes aiohttp for extreme speed.

## 🚀 Features
- **Universal Target Engine:** Enter any Graphy base url (e.g. `learn.coachbsr.com` or `courses.atishmathur.com`)
- **Dual Support Input:** Check items via text paste or uploading combo `.txt` files directly in Telegram. 
- **Spayee Token Bypass:** Catches the internal `c_ujwt` dropping for 100% accurate auth checks, completely eliminating false negatives.
- **Dynamic Course Parsers:** Four embedded regex strategies to fetch `window.__INITIAL_STATE__` / UI HTML states from `mycourses`, `activeCourses`, and `store` modules.
- **Async Threading Bypass:** Employs rate limiting Semaphore to ensure the target infrastructure's CloudFlare WAF doesn't ban your IP.

---

## ⚡ Direct Deployment

You can host this bot quickly using direct deploy on Heroku! Ensure you have your `API_ID` & `API_HASH` from [my.telegram.org](https://my.telegram.org) and your `BOT_TOKEN` from [@BotFather](https://t.me/BotFather).

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/Shreerambro/graphy-checker)

---

## 💻 Local Testing / VPS Deployment

1. Clone or download this repository.
2. Install Python 3 requirements:
```bash
pip install -r requirements.txt
```
3. Set your environment variables (Windows / Linux):
```bash
# Windows
set API_ID=1234567
set API_HASH=your_api_hash
set BOT_TOKEN=your_bot_token

# Linux/MacOS
export API_ID=1234567
export API_HASH=your_api_hash
export BOT_TOKEN=your_bot_token
```
4. Run the bot:
```bash
python bot.py
```

## 🎮 Telegram Usage
Once your bot is on:
1. Send `/start` to verify it's online.
2. Send `/graphy` to begin the Universal Target sequence.
3. Follow the Prompts!
4. Check your real-time updating Hits dashboard.

*Disclaimer: This is developed exclusively for Ethical Bug Bounty Research and Network Auth evaluation routines.*
