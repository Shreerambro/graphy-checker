# Graphy Universal Checker Bot

Universal Telegram Bot to check accounts on ANY Graphy/Spayee platform with full course extraction using headless browser.

## Features
- **Universal:** Works with any Graphy base URL
- **Dual Input:** Text paste or `.txt` file combos
- **Fast Auth:** aiohttp-based login (HIT/BAD in milliseconds)  
- **Playwright Course Extraction:** Headless Chromium renders the React page and extracts real course names
- **Live Dashboard:** Real-time progress updates in Telegram
- **Stop Control:** `/stop_graphy` to abort mid-check

## Deploy to Heroku

### Step 1: Add Buildpacks
```bash
heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-apt
heroku buildpacks:add --index 2 heroku/python
```

### Step 2: Set Config Vars
```bash
heroku config:set API_ID=your_api_id
heroku config:set API_HASH=your_api_hash
heroku config:set BOT_TOKEN=your_bot_token
```

### Step 3: Deploy
```bash
git push heroku main
```

### Step 4: Scale Worker
```bash
heroku ps:scale worker=1
```

## Local Setup
```bash
pip install -r requirements.txt
playwright install chromium

# Set env vars
export API_ID=123456
export API_HASH=your_hash
export BOT_TOKEN=your_token

python bot.py
```

## Bot Commands
| Command | Description |
|---------|-------------|
| `/start` | Bot info |
| `/graphy` | Start checker |
| `/stop_graphy` | Stop active check |

## How It Works
1. **Login Phase:** Fast POST request via aiohttp checks credentials
2. **Course Phase:** Only on HIT - Playwright opens headless Chromium, logs in, navigates to courses page, waits for React to render, then scrapes course names from DOM
3. **Report:** Real-time alerts + final hits file

## Architecture
```
User -> /graphy -> Base URL -> Combos
                                  |
                          aiohttp POST login
                           /           \
                         BAD           HIT
                          |             |
                        skip    Playwright Browser
                                    |
                              Navigate to courses
                                    |
                              Extract DOM titles
                                    |
                              Send to Telegram
```
