# Telegram Batch Media Forwarder & Auto-Link Tool

An automated, risk-protected tool to batch-forward media (videos, photos, files) from a Telegram Channel into a File Store Bot, automate the inline button clicks, and save generated access links into a text file.

---

## ⚠️ Important Risks & Safety Notice (Please Read)

1. **Telegram Anti-Spam & Rate Limits (`FloodWait`):**
   - Forwarding hundreds of files rapidly from a personal account will trigger Telegram's anti-spam detection.
   - If triggered, Telegram forces a `FloodWait` (pausing your account for anywhere from 30 seconds to several hours). In severe cases (especially on brand-new accounts), it can cause temporary account restrictions or bans.
   - **Protection in this script:** 
     - **Safe Pacing:** A random delay (2.0 to 4.0 seconds) between every forwarded file.
     - **Batch Cooldown:** A 15-second rest after each batch of 100 files.
     - **FloodWait Shield:** If Telegram asks to pause, the script automatically waits out the timer and resumes without crashing.

2. **Account Age Recommendation:**
   - **DO NOT** use an account created within the last 1-2 weeks. Use an established account with 2FA enabled, or a secondary dedicated account.

3. **Total Estimated Time for 1,000 Files:**
   - With safe delays: ~1,000 files * 2.5s avg + pauses ≈ **42 to 45 minutes**.
   - Do not rush this—patience is what keeps your Telegram account 100% safe!

4. **Crash & Disconnect Resilience:**
   - The tool maintains `progress.json`. If you close the window, disconnect, or press `Ctrl + C`, it saves its exact spot. When you reopen it, it skips already forwarded files and resumes cleanly.

---

## 🛠️ Step-by-Step Setup Guide

### Step 1: Get your Telegram API Credentials (Free & 2 Minutes)
Telegram requires an `api_id` and `api_hash` to allow scripts to interact with your account:
1. Go to **[https://my.telegram.org](https://my.telegram.org)** in your web browser.
2. Log in using your Telegram phone number (Telegram will send a confirmation code to your Telegram app).
3. Click on **API development tools**.
4. Fill in any name for **App title** and **Short name** (e.g. `MyForwarder`).
5. Click **Create application**.
6. You will see your **`api_id`** (a number) and **`api_hash`** (a string of letters and numbers). Copy them.

---

### Step 2: Configure `config.json`
Open `config.json` in Notepad or any text editor:
```json
{
    "api_id": 12345678,
    "api_hash": "0123456789abcdef0123456789abcdef",
    "phone_number": "+1234567890",
    "source_channel": "@YourSourceChannel",
    "target_bot": "@YourTargetBot",
    "batch_size": 100,
    "min_delay_seconds": 2.0,
    "max_delay_seconds": 4.0,
    "batch_wait_seconds": 15.0,
    "button_1_text_or_index": 0,
    "button_2_text_or_index": 0
}
```

#### Settings explanation:
- **`api_id`**: The number from my.telegram.org.
- **`api_hash`**: The string from my.telegram.org.
- **`phone_number`**: Your phone number with country code (e.g., `+1...` or `+91...`).
- **`source_channel`**: The username of your channel (e.g., `@MyChannel`) or channel link / chat ID. Make sure your Telegram account has joined or is admin in this channel.
- **`target_bot`**: The username of the bot (e.g., `@FileStoreBot`).
- **`batch_size`**: Number of files before clicking buttons (default is `100`).
- **`button_1_text_or_index`**: Which button to click first. You can use `0` for the first button, or write text that matches the button (e.g., `"Generate"` or `"Done"`).
- **`button_2_text_or_index`**: Which button to click second. Use `0` for the first button, or write matching text (e.g., `"Confirm"`).

---

### Step 3: Run the Tool
Simply **double-click `run.bat`**.

You will see an interactive menu:
```
Please choose an option:
  [1] Start Forwarding (Automatic, Safe Pacing, Auto-Resume)
  [2] Dry Run (Scan channel & count files without forwarding)
  [3] Test Bot Buttons (Inspect & test clicking bot's buttons)
  [4] Reset Progress (Clear progress.json to restart from scratch)
  [5] Exit
```

- **First Run Authentication:**
  The first time you run it, Telegram will ask for a login code in the console (sent to your Telegram app). Enter it, and if you have 2FA enabled, enter your password. This generates `user_session.session`, so you only log in once!
- **Recommended First Action:**
  Select **[2] Dry Run** first to verify that your channel is found and check the total file count.
- Then select **[1] Start Forwarding** to run the complete forwarder.

---

### Step 4: Access Your Links
Once each batch of 100 completes, the script captures the link and saves it to:
📄 **`generated_links.txt`**
