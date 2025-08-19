---

# 🤖 Telegram Media Downloader Bot

A powerful and user-friendly Telegram bot that allows users to **log in with their own accounts** and **download media from message links** — all via a secure interface and admin dashboard.

---

## 🌟 Features

✅ User login via phone number and 2FA (if enabled)  
📥 Download media from public and private Telegram message links  
🔐 Encrypted session storage using Fernet encryption  
📊 Admin panel with stats, user listing, and ban functionality  
🚫 User banning system  
📈 Track statistics like codes sent and registered users  
🔍 Admin user search via ID, phone, or username

---

## 🛠️ Requirements

- Python 3.8+
- Telegram API credentials (`api_id`, `api_hash`, `bot_token`)
- [Telethon](https://github.com/LonamiWebs/Telethon)
- [cryptography](https://cryptography.io/)
- [aiosqlite](https://github.com/omnilib/aiosqlite)

Install dependencies with:

```bash
pip install -r requirements.txt
````

---

## ⚙️ Setup

1. **Clone this repository:**

```bash
git clone https://github.com/Aayco/SaveBot.git
cd SaveBot
```

2. **Create your `config.json` file:**

```json
{
  "bot_token": "bot_token",
  "comment": "Get them from https://my.telegram.org/apps"
  "api_id": api_id,
  "api_hash": "api_hash",
  "admins": [5541407305, 7742838492],
  "fernet_key": "Cryptography fernet key"
}
```

> 🔐 Generate a Fernet key using:
>
> ```python
> from cryptography.fernet import Fernet
> print(Fernet.generate_key().decode())
> ```

3. **Directory Structure:**

```
📁 SaveBot/
├── bot.py                   # Main bot code
├── utils.py                 # CryptoManager (for encryption/decryption)
├── helpers.py               # Date helper
├── config.json              # Your bot credentials
├── requirements.txt         # Python dependencies
```

---

## 🚀 Running the Bot

To run the bot:

```bash
python bot.py
```

The bot will initialize the SQLite database (`database.db`), create required tables, and start listening for messages.

---

## 🔐 How It Works

### 👤 User Flow

* **User joins bot ➡️ Presses login ➡️ Enters phone number**
* **Receives code ➡️ Enters code ➡️ Optionally enters 2FA password**
* **After login ➡️ Can download media via Telegram message link**

### 🛡 Admin Features

Admins can:

* View user stats
* List all users
* Search user by ID, phone, or username
* Ban users from using the bot

---

## 🔒 Security Notes

* All sessions and passwords are encrypted with Fernet before saving.
* Admins are defined in the `config.json` via user IDs.
* Database is local (`SQLite`), and access should be secured in production.

---

## 📸 Screenshots (Optional)

*You can add Telegram UI screenshots here for better visualization.*

---

## 🧠 Credits

* Built using [Telethon](https://github.com/LonamiWebs/Telethon)
* Encryption via [cryptography](https://cryptography.io/)

---

## 🤝 Contribution

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

---
