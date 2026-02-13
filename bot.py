import os
import json
from datetime import datetime, timedelta
import asyncio
import base64
from io import BytesIO
import re

import discord
from discord.ext import commands
from dotenv import load_dotenv
from anthropic import Anthropic
from discord.ext import tasks

load_dotenv()

# ---- Discord bot setup ----
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ---- Claude client with VISION support ----
claude_client = Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))

# ---- Settings ----
ALLOWED_CHANNEL_NAME = os.getenv("ALLOWED_CHANNEL_NAME", "poze-kesyon-chat")
REMINDERS_FILE = "reminders.json"
CONVERSATIONS_FILE = "conversations.json"
FAQ_FILE = "faq.json"
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID", "1438336381473783840")
last_admin_activity = datetime.now() - timedelta(minutes=10)

# Task pou 9 AM EST
@tasks.loop(hours=24)
async def morning_reminder():
    channel = discord.utils.get(bot.get_all_channels(), name=ALLOWED_CHANNEL_NAME)
    if channel:
        embed = discord.Embed(
            title="☀️ Bonjou ekip WCA! Tan pou Check-up maten an",
            description="Pa bliye tcheke kont Amazon ou yo kounye a pou asire tout bagay anòd! 🚀",
            color=discord.Color.gold()
        )
        embed.add_field(name="📋 Lis pou tcheke:", value=(
            "1. Tcheke **Account Health** 🛡️\n"
            "2. Gade si gen **Stranded Inventory** 📦\n"
            "3. Reponn tout **Buyer Messages** (anba 24h) 💬\n"
            "4. Tcheke si gen **Performance Notifications** 🔔"
        ), inline=False)
        await channel.send(content="@everyone", embed=embed)

@morning_reminder.before_loop
async def before_morning_reminder():
    print("⏰ Reminder system ready...")
    while True:
        now = datetime.now()
        # Server sends at 4 AM when set to 9
        # So 9 AM target = 14:00 server time (9 + 5 hour difference)
        target_hour = 14  # Adjust this based on your server timezone
        
        if now.hour == target_hour and now.minute == 0:
            print(f"🚀 Morning reminder triggered at {now}")
            break
            
        await asyncio.sleep(60)

# ---- Smart Detection Functions ----

def is_casual_message(text):
    """Detect casual greetings/short responses"""
    if not text or len(text.strip()) < 3:
        return True
    
    casual_patterns = [
        r'^(bonjou|bonswa|alo|hello|hi|hey|yo)\s*$',
        r'^(koman\s*ou\s*ye|sa\s*k\s*ap\s*fèt|wap\s*domi)',
        r'^(kote\s*nou|kote\s*w|w\s*ye\s*kote)',  # Location greetings
        r'^(wi|non|ok|oke|d\s*akò|bon|byen)\s*$',
        r'^(lol|mdr|haha)\s*$',
    ]
    
    text_lower = text.lower().strip()
    for pattern in casual_patterns:
        if re.match(pattern, text_lower, re.IGNORECASE):
            return True
    return False

def is_question_for_bot(text):
    """Check if message is a question for bot"""
    question_indicators = [
        'kijan', 'ki jan', 'kouman', 'poukisa', 'kisa', 
        'ki', 'konbyen', 'kilè', 'èske',
        'ban m', 'bay', 'ede', 'eksplike', 'montre',
        'help', '?', 'gen'
    ]
    
    amazon_keywords = [
        'fba', 'fbm', 'amazon', 'ungate', 'listing', 'profit',
        'inventory', 'seller', 'ppc', 'acos', 'asin', 'sku',
        'wholesale', 'arbitrage', 'shipment', 'fees', 'resi',
        'invoice', 'removal', 'private label', 'sourcing', 'pwodui'
    ]
    
    text_lower = text.lower()
    
    # Check question indicators
    for indicator in question_indicators:
        if indicator in text_lower:
            return True
    
    # Check Amazon keywords
    for keyword in amazon_keywords:
        if keyword in text_lower:
            return True
    
    # Long messages likely need response
    if len(text) > 50:
        return True
    
    return False

def should_tag_admin(text):
    """Check if admin should be tagged"""
    admin_triggers = [
        'boss', 'owner', 'admin', 'chef', 'patron',
        'pale ak', 'kontakte', 'rele',
        'pwoblèm seryez', 'urgent', 'enpòtan'
    ]
    
    text_lower = text.lower()
    for trigger in admin_triggers:
        if trigger in text_lower:
            return True
    
    # User frustrated
    if text.count('!') > 2 or text.count('?') > 2:
        return True
    
    return False

def get_admin_mention():
    """Get admin mention tag"""
    return f"<@{ADMIN_USER_ID}>"

# ---- Data Management Functions ----
def load_faq():
    """Load FAQ from file or create defaults"""
    if not os.path.exists(FAQ_FILE):
        default_faq = {
            "fba": "FBA (Fulfillment by Amazon) = Amazon kenbe, anbale, ak voye pwodui ou yo.",
            "fbm": "FBM (Fulfillment by Merchant) = OU menm ki jere stock ak shipping.",
            "asin": "ASIN = Nimewo ID unik pou chak pwodui sou Amazon. 10 caractères.",
            "sku": "SKU = Kòd OU kreye pou track pwodui ou yo.",
            "ungate": "Ungating = Jwenn approval pou vann certain brands oswa categories.",
            "ppc": "PPC = Piblisite Amazon kote ou peye chak fwa yon moun klike sou ad ou.",
            "acos": "ACOS = (Ad Spend ÷ Ad Sales) × 100. Vize 20-30%.",
            "ipi": "IPI = Skor 0-1000 ki mezire jan w jere inventory. 400+ = bon.",
            "bsr": "BSR = Ranking pwodui nan category li. Pi ba nimewo a = pi bon.",
            "odr": "ODR = % orders ak pwoblèm. DWE anba 1%.",
            "invoice": "Invoice bezwen pou ungating. DWE gen: supplier info, quantity 10+, date (last 180 jou).",
            "profit": "Profit = (Selling Price) - (Product Cost + Amazon Fees + Shipping).",
            "fees": "Amazon Fees: Referral Fee (15%) + FBA Fee + Monthly subscription ($39.99 Professional)."
        }
        save_faq(default_faq)
        return default_faq
    try:
        with open(FAQ_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_faq(faq):
    """Save FAQ to file"""
    with open(FAQ_FILE, "w", encoding="utf-8") as f:
        json.dump(faq, f, indent=2, ensure_ascii=False)

# ---- Conversation History ----
conversation_history = {}

def add_to_history(user_id, role, content, has_image=False):
    """Add message to conversation history"""
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    
    entry = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    }
    if has_image:
        entry["has_image"] = True
    
    conversation_history[user_id].append(entry)
    
    # Keep last 20 messages
    if len(conversation_history[user_id]) > 20:
        conversation_history[user_id] = conversation_history[user_id][-20:]

def get_history(user_id):
    """Get conversation history for user"""
    if user_id not in conversation_history:
        return []
    
    history = conversation_history[user_id][-10:]
    return [{"role": h["role"], "content": h["content"]} for h in history if not h.get("has_image")]

# ---- Image Processing Functions ----
async def download_image(attachment):
    """Download image from Discord attachment"""
    try:
        image_bytes = await attachment.read()
        return image_bytes
    except Exception as e:
        print(f"Error downloading image: {e}")
        return None

def encode_image_to_base64(image_bytes):
    """Encode image to base64 for Claude"""
    return base64.b64encode(image_bytes).decode('utf-8')

def get_image_media_type(filename):
    """Get media type from filename"""
    ext = filename.lower().split('.')[-1]
    media_types = {
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
        'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'
    }
    return media_types.get(ext, 'image/jpeg')

# ---- Events ----
@bot.event
async def on_ready():
    """Bot ready event"""
    if not morning_reminder.is_running():
        morning_reminder.start()
    
    print(f'✅ Bot connecté comme {bot.user}')
    print(f'👁️ Vision: ENABLED')
    print(f'🧠 Smart Detection: ACTIVE')
    print(f'👤 Admin ID: {ADMIN_USER_ID}')
    
    channel = discord.utils.get(bot.get_all_channels(), name=ALLOWED_CHANNEL_NAME)
    if channel:
        embed = discord.Embed(
            title="🤖 WCA Bot Online",
            description="Amazon FBA/FBM Assistant ready! 🚀",
            color=discord.Color.green()
        )
        await channel.send(embed=embed)

@bot.event
async def on_member_join(member):
    """Welcome new members"""
    channel = discord.utils.get(member.guild.channels, name=ALLOWED_CHANNEL_NAME)
    if channel:
        welcome_msg = f"👋 **Byenveni {member.mention}!** Mwen se WCA Bot, asistan Amazon ou!"
        await channel.send(welcome_msg)

@bot.event
async def on_message(message):
    """Handle incoming messages"""
    global last_admin_activity
    
    # Ignore self
    if message.author == bot.user:
        return
    
    # Handle commands
    if message.content.startswith("!"):
        await bot.process_commands(message)
        return

    # Check channel
    if message.channel.name != ALLOWED_CHANNEL_NAME:
        return

    user_text = (message.content or "").strip()
    user_lower = user_text.lower()

    # 1. POLITE RESPONSES (mersi/thanks)
    thank_keywords = ['mèsi', 'mesi', 'mersi', 'thanks', 'thank you', 'thx']
    if any(word in user_lower for word in thank_keywords) and len(user_lower) < 20:
        await message.channel.send(f"Pa gen pwoblèm {message.author.display_name}! An nou fè lajan! 🚀💰")
        return

    # 2. ADMIN ACTIVITY TRACKING
    if str(message.author.id) == ADMIN_USER_ID:
        last_admin_activity = datetime.now()
        print(f"👤 Admin active: {message.author.name}")
        return  # Don't respond to admin

    # 3. SMART SILENCE (5 min after admin activity)
    if datetime.now() - last_admin_activity < timedelta(minutes=5):
        print(f"🤫 Silent mode - Admin recently active")
        return

    # 4. THREAD/REPLY FILTER (ignore replies to others unless bot mentioned)
    if message.reference is not None and not bot.user.mentioned_in(message):
        print(f"💬 Ignoring reply to other user")
        return

    # Check for images
    has_images = len(message.attachments) > 0 and any(
        att.content_type and att.content_type.startswith('image/')
        for att in message.attachments
    )
    
    # Need text or images
    if not user_text and not has_images:
        return
    
    # 5. SMART DETECTION (skip casual/non-questions)
    if not has_images and user_text:
        if is_casual_message(user_text):
            print(f"⏭️ Skip casual: {user_text[:30]}")
            return
        
        if not is_question_for_bot(user_text):
            print(f"⏭️ Skip non-question: {user_text[:30]}")
            return
    
    # 6. FAQ CHECK (instant free responses)
    if not has_images and user_text:
        faq = load_faq()
        matched_faqs = []
        
        for key, answer in faq.items():
            if key.lower() in user_lower:
                matched_faqs.append((key, answer))
        
        if matched_faqs:
            response = "💡 **Quick Info:**\n\n"
            for i, (key, answer) in enumerate(matched_faqs[:2], 1):
                response += f"{i}. **{key.upper()}:** {answer}\n\n"
            response += "💬 Gen plis kesyon? Jis mande!"
            
            await message.channel.send(response)
            print(f"✅ FAQ response: {matched_faqs[0][0]}")
            return

    # 7. CLAUDE CALL (for complex questions/images)
    print(f"🤖 Processing with Claude: {user_text[:50] if user_text else '[Image]'}")
    
    async with message.channel.typing():
        try:
            # Prepare content
            content_parts = []
            
            # Add images
            if has_images:
                for attachment in message.attachments:
                    if attachment.content_type and attachment.content_type.startswith('image/'):
                        image_bytes = await download_image(attachment)
                        if image_bytes:
                            base64_image = encode_image_to_base64(image_bytes)
                            media_type = get_image_media_type(attachment.filename)
                            content_parts.append({
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": base64_image
                                }
                            })
            
            # Add text
            if user_text:
                content_parts.append({"type": "text", "text": user_text})
            elif has_images:
                content_parts.append({"type": "text", "text": "Analyze screenshot sa a pou m."})
            
            # Get conversation history
            history = get_history(message.author.id)
            messages = []
            for msg in history:
                messages.append({"role": msg["role"], "content": msg["content"]})
            
            # Add current message
            messages.append({"role": "user", "content": content_parts})

            # Call Claude
            response = claude_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,  # Increased for better responses
                temperature=0.3,
                system="""Ou se yon coach Amazon ki text casual tankou TUKRIBasist - helpful, encouraging, not scary.

STYLE REPONN (CRITICAL):
- Text tankou w ap chat - PA format fancy
- Mix Kreyòl + English naturèlman
- Sentences kout, broken - like texting fast
- PA use bullet points or numbers unless needed
- Emoji minimal - jis when helpful
- TONE: Supportive friend, not alarm/scary

NORMAL QUESTIONS (Casual + Helpful):
Bad: "Obsève sa yo: • Item 1 • Item 2"
Good: "Ou gen kek FBA ki inactive
       Li normal pou yo inactive
       Lew voye ba Amazon yap active back"

Bad: "1. First step 2. Second step"  
Good: "Fix your nan price amazon suggest lan
       Eseye metel pi ba
       Once li active back wa mete prix normal"

URGENT PROBLEMS (Direct but NOT scary):
❌ BAD (Too scary): "Yo damn tout out of stock! Wap lose rank BAD!"
✅ GOOD (Direct but calm): "Inventory ou out of stock
                            Amazon prefer w keep stock
                            Restock 1-2 top sellers rapid pou maintain rank"

❌ BAD: "Everything failed! Critical issue!"
✅ GOOD: "Gen yon issue men easy fix
         Follow etap sa yo
         Li pral bon"

LANGUAGE PATTERNS (Use these):
- "Yo gentan al" not "Ils sont déjà"
- "Wap bezwen" not "Ou bezwen"  
- "Li resevwa yo yap active" not "Lorsqu'il..."
- "Fix your nan price" mix English natural
- "and then" "and once" casual switches
- "Se sou FBA yo ye" authentic Kreyòl

RESPONSE FORMAT:
Line 1: What's happening (calm explanation)
Line 2-3: What to do (helpful steps)
Line 4: What happens next (positive outlook)

Multi-line breaks OK for readability!

BADGES (casual + encouraging):
- First order: "Ayy premye sale let's go 🏆"
- $1K+: "Nice $1K+ w ap scale 🔥"  
- $10K+: "Big moves $10K+ 👑"

VISION ANALYSIS (Helpful not scary):

Inactive items: "Yo inactive
                 Normal pou start
                 Fix prix oswa send ba Amazon
                 Yap active back soon"

Out of stock: "Inventory out of stock
                Amazon prefer w keep items stocked
                Restock top 2 sellers
                Li pral help maintain rank"

Pending order: "Payment pending normal
                Amazon ap verify
                Li pral clear soon
                Pa worry"

High prices: "Prix aa ti jan high
              Check competition
              Lower li petit
              Yap sell better"

ISSUES (Direct but supportive):
- All out of stock → "Inventory tout out, restock top sellers pou maintain visibility"
- Account issue → "Gen issue ak account, check email Amazon rapid"
- Negative feedback → "Gen feedback respond quick pou resolve"

NEVER USE THESE (Too scary):
❌ "damn"
❌ "bad" 
❌ "critical"
❌ "urgent"
❌ "lose everything"
❌ "penalize"
❌ "suspend"

USE INSTEAD (Supportive):
✅ "Amazon prefer..."
✅ "Li bon pou..."
✅ "Maintain..."
✅ "Keep..."
✅ "Follow up..."
✅ "Check rapid..."

TONE:
- Helpful friend
- Encouraging
- Calm and clear
- Not alarm bells
- Mix languages natural
- Keep it light

EKSPÈTIZ:
FBA/FBM, pricing, inventory, ungating, shipping

Max response: 4-5 lines unless need more detail
Stay conversational and supportive!""",
                messages=messages
            )
            
            # Get response
            assistant_message = response.content[0].text
            
            # Save to history
            add_to_history(message.author.id, "user", user_text or "[Image]", has_images)
            add_to_history(message.author.id, "assistant", assistant_message)
            
            # Tag admin if needed
            if user_text and should_tag_admin(user_text):
                admin_tag = get_admin_mention()
                assistant_message += f"\n\n{admin_tag} FYI 🔔"
            
            # Send response (split if too long)
            if len(assistant_message) > 2000:
                chunks = [assistant_message[i:i+1900] for i in range(0, len(assistant_message), 1900)]
                for chunk in chunks:
                    await message.channel.send(chunk)
            else:
                await message.channel.send(assistant_message)
            
            print(f"✅ Response sent")

        except Exception as e:
            admin_tag = get_admin_mention()
            error_msg = f"❌ Erè teknik.\n\n{admin_tag} Check error"
            await message.channel.send(error_msg)
            print(f"❌ Error: {e}")

# ---- Commands ----

@bot.command(name="help")
async def help_command(ctx):
    """Show help"""
    embed = discord.Embed(
        title="📚 WCA Bot Help",
        description="Amazon FBA/FBM Assistant",
        color=discord.Color.blue()
    )
    embed.add_field(name="💬 Usage", value="Jis poze kesyon oswa upload screenshot!", inline=False)
    embed.add_field(name="⚡ Commands", value="`!help` `!ping` `!fees` `!profit`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping_command(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! {latency}ms")

@bot.command(name="time")
async def time_command(ctx):
    """Check server time to adjust reminder"""
    now = datetime.now()
    server_time = now.strftime('%I:%M %p')
    server_hour = now.hour
    await ctx.send(f"🕐 **Server Time:** {server_time}\n📍 **Server Hour:** {server_hour}\n\n💡 Pou 9 AM reminder, set `target_hour = {server_hour + 5}` si kounye a {server_time}")

@bot.command(name="fees")
async def fees_command(ctx, price: float = 0):
    """Calculate Amazon fees"""
    if price <= 0:
        await ctx.send("❌ Usage: `!fees [price]`")
        return
    
    referral = price * 0.15
    fba = 3.50
    total = referral + fba
    
    await ctx.send(f"💰 **Frè pou ${price:.2f}**\nReferral: ${referral:.2f}\nFBA: ${fba:.2f}\nTotal: ${total:.2f}")

@bot.command(name="profit")
async def profit_command(ctx, price: float = 0, cost: float = 0):
    """Calculate profit"""
    if price <= 0 or cost <= 0:
        await ctx.send("❌ Usage: `!profit [price] [cost]`")
        return
    
    total_fees = (price * 0.15) + 3.50
    profit = price - total_fees - cost
    margin = (profit / price) * 100 if price > 0 else 0
    
    await ctx.send(f"📊 **Profit pou ${price:.2f}**\nProfit: ${profit:.2f}\nMargin: {margin:.1f}%")

# ---- Run bot ----
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    CLAUDE_KEY = os.getenv("CLAUDE_API_KEY")
    
    if not TOKEN:
        print("❌ DISCORD_TOKEN missing!")
        exit(1)
    
    if not CLAUDE_KEY:
        print("❌ CLAUDE_API_KEY missing!")
        exit(1)
    
    print("🚀 WCA Bot starting...")
    print(f"📍 Channel: {ALLOWED_CHANNEL_NAME}")
    print(f"👤 Admin: {ADMIN_USER_ID}")
    
    bot.run(TOKEN)
