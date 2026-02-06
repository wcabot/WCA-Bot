import os
import json
import datetime
import asyncio
import base64
import re
from io import BytesIO

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
# ---- Discord bot setup ----
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# ---- 2. Kreye Bot la (Imedyatman apre intents) ----
bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command('help')

# ---- Claude client with VISION support ----
claude_client = Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))

# ---- Settings ----
ALLOWED_CHANNEL_NAME = os.getenv("ALLOWED_CHANNEL_NAME", "poze-kesyon-chat")
REMINDERS_FILE = "reminders.json"
CONVERSATIONS_FILE = "conversations.json"
FAQ_FILE = "faq.json"
# ---- 1. TRAVAY OTOMATIK (TASKS) ----
@tasks.loop(time=datetime.time(hour=9, minute=0))
async def morning_reminder():
    channel = discord.utils.get(bot.get_all_channels(), name=ALLOWED_CHANNEL_NAME)
    if channel:
        embed = discord.Embed(
            title="☀️ Bonjou Fanmi WCA!",
            description="Pa bliye rityèl maten an:\n\n✅ **Tcheke Account Health** (Vize 200+)\n✅ **Reponn mesaj kliyan** (Anba 24h)\n✅ **Voye screenshot** si w bloke nan yon kòmand!",
            color=discord.Color.gold()
        )
        await channel.send(embed=embed)
# ---- Data Management Functions ----
def load_faq():
    if not os.path.exists(FAQ_FILE):
        default_faq = {
            # Amazon Basics
            "fba": "FBA (Fulfillment by Amazon) = Amazon kenbe, anbale, ak voye pwodui ou yo. Ou voye inventory nan warehouse Amazon, yo jere tout shipping.",
            "fbm": "FBM (Fulfillment by Merchant) = OU menm ki jere stock ak shipping. Ou kenbe inventory lakay ou oswa nan warehouse ou.",
            "asin": "ASIN (Amazon Standard Identification Number) = Nimewo ID unik pou chak pwodui sou Amazon. 10 caractères (B001234567).",
            "sku": "SKU (Stock Keeping Unit) = Kòd OU kreye pou track pwodui ou yo. Ou chwazi kijan w vle li ye.",
            
            # Ungating & Approval
            "ungate": "Ungating = Jwenn approval pou vann certain brands oswa categories sou Amazon. Ou bezwen invoice wholesale oswa authorization letter.",
            "gated": "Gated brand/category = Brand oswa category ki bezwen Amazon approval anvan ou ka vann. Egzanp: Nike, Apple, Grocery.",
            "ungating": "Ungating se process pou jwenn permission vann gated brands. Bezwen: invoice wholesale (10+ units), authorization letter, oswa sales history.",
            
            # Advertising
            "ppc": "PPC (Pay-Per-Click) = Piblisite Amazon kote ou peye chak fwa yon moun klike sou ad ou. Types: Sponsored Products, Brands, Display.",
            "acos": "ACOS (Advertising Cost of Sale) = (Ad Spend ÷ Ad Sales) × 100. Egzanp: $30 spend, $100 sales = 30% ACOS. Vize 20-30%.",
            "cpc": "CPC (Cost Per Click) = Konbyen ou peye chak fwa yon moun klike sou ad ou. Depends on keywords ak competition.",
            
            # Metrics
            "ipi": "IPI (Inventory Performance Index) = Skor 0-1000 ki mezire jan w jere inventory. 400+ = bon, 350- = risk storage limits.",
            "bsr": "BSR (Best Sellers Rank) = Ranking pwodui nan category li. #1 = top seller. Pi ba nimewo a = pi bon.",
            "odr": "ODR (Order Defect Rate) = % orders ak pwoblèm (negative feedback, A-Z claims, chargebacks). DWE anba 1%.",
            
            # Operations  
            "removal order": "Removal Order = Mande Amazon retounen oswa detui inventory FBA ou. Use lè: pwodwi pa vann, expired, oswa ou vle chanje supplier.",
            "stranded inventory": "Stranded Inventory = Pwodwi ki nan warehouse Amazon men pa ka vann (listing deleted oswa suppressed). Fix rapid!",
            "long term storage": "Long-Term Storage Fees = Frè Amazon chaje si pwodwi ou rete nan warehouse 365+ jou. $6.90/cubic foot/month!",
            
            # Sourcing
            "wholesale": "Wholesale = Achte pwodwi nan gwo volim dirèkteman depi manufacturer oswa distributor pou revann sou Amazon.",
            "arbitrage": "Retail Arbitrage = Achte pwodwi sou sale nan magazen (Walmart, Target) epi revann yo sou Amazon pou profit.",
            "private label": "Private Label = Kreye pwòp brand ou. Achte generic pwodwi, mete logo ou, vann li sou Amazon.",
            
            # Documents
            "resi": "Resi/Invoice = Dokiman ki montre ou achte pwodwi legally. Bezwen pou ungating. DWE gen: supplier info, 10+ units, date.",
            "invoice": "Invoice bezwen pou ungating. DWE include: supplier name/address, ou name/address, pwodwi details, quantity 10+, date (last 180 jou).",
            
            # Common Questions
            "kouman pou vann": "Pou vann sou Amazon: 1) Kreye Seller account, 2) Find profitable pwodwi, 3) Source li, 4) Create listing, 5) Ship to FBA oswa FBM.",
            "profit": "Profit = (Selling Price) - (Product Cost + Amazon Fees + Shipping). Vize minimum 25-30% profit margin.",
            "fees": "Amazon Fees: Referral Fee (15% average) + FBA Fee ($3-5 typical) + Monthly subscription ($39.99 Professional)."
        }
        save_faq(default_faq)
        return default_faq
    try:
        with open(FAQ_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_faq(faq):
    with open(FAQ_FILE, "w", encoding="utf-8") as f:
        json.dump(faq, f, indent=2, ensure_ascii=False)

# ---- Conversation History ----
conversation_history = {}

def add_to_history(user_id, role, content, has_image=False):
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    
    entry = {
        "role": role,
        "content": content,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    if has_image:
        entry["has_image"] = True
    
    conversation_history[user_id].append(entry)
    
    # Kenbe 20 dènye mesaj sèlman
    if len(conversation_history[user_id]) > 20:
        conversation_history[user_id] = conversation_history[user_id][-20:]

def get_history(user_id):
    if user_id not in conversation_history:
        return []
    # Retounen sèlman 10 dènye mesaj pou context (san imaj pou save tokens)
    history = conversation_history[user_id][-10:]
    # Filter out image references for context
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
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'webp': 'image/webp'
    }
    return media_types.get(ext, 'image/jpeg')

# ---- 4. EVENTS DISCORD ----
@bot.event
async def on_ready():
    print(f'✅ Bot konekte kòm {bot.user}')
    # Sèlman kòmanse si li pa t ap kouri deja
    if not morning_reminder.is_running():
        morning_reminder.start()
# ---- Event: Member Join ----
@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.channels, name=ALLOWED_CHANNEL_NAME)
    if channel:
        welcome_msg = f"""
👋 **Byenveni {member.mention}!**

Mwen se **WCA Bot**, asistan Amazon FBA/FBM ou a! 📦

✨ **Mwen ka ede w avèk:**
- Product listing & optimization
- FBA/FBM questions
- Shipping & inventory
- PPC advertising
- Account health
- **📸 Analyze screenshots!**
- Epi anpil lòt bagay!

💬 **Pou kòmanse:** Jis poze m yon kesyon!
📸 **Pou analyze imaj:** Upload screenshot epi di m sa w vle konnen!
📚 **Pou wè tout kòmandman:** Tape `!help`

Let's grow your Amazon business together! 🚀
"""
        await channel.send(welcome_msg)

# ---- Event: Respond to messages ----
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # Kite commands travay tou
    if message.content.startswith("!"):
        await bot.process_commands(message)
        return
    
    # Check si se bon channel (IMPORTANT pou economize API calls)
    if message.channel.name != ALLOWED_CHANNEL_NAME:
        return
    
    user_text = (message.content or "").strip()
    
    # Check if there are images attached
    has_images = len(message.attachments) > 0 and any(
        att.content_type and att.content_type.startswith('image/')
        for att in message.attachments
    )
    
    if not user_text and not has_images:
        return
    
    # ⚡ CHECK FAQ FIRST - Economize Claude API calls!
    if not has_images and user_text:
        faq = load_faq()
        matched_faqs = []
        
        # Check si user_text match exactly yon FAQ key
        user_lower = user_text.lower().strip()
        
        for key, answer in faq.items():
            # Exact match oswa close match
            if key.lower() in user_lower or user_lower in key.lower():
                matched_faqs.append((key, answer))
        
        # Si gen FAQ match, reponn dirèkteman SAN rele Claude!
        if matched_faqs:
            response = "💡 **Quick Info:**\n\n"
            for i, (key, answer) in enumerate(matched_faqs[:2], 1):  # Max 2 FAQs
                response += f"{i}. **{key.upper()}:** {answer}\n\n"
            
            response += "💬 Gen plis kesyon? Jis mande!"
            
            await message.channel.send(response)
            return  # ← PA RELE CLAUDE!
    
    # Si FAQ pa reponn → Rele Claude
    # Async typing indicator
   # Si FAQ pa reponn → Rele Claude
    async with message.channel.typing():
        try:
            # Prepare content list for Claude
            content_parts = []
            
            # Add images first if present
            if has_images:
                for attachment in message.attachments:
                    if attachment.content_type and attachment.content_type.startswith('image/'):
                        print(f"📸 Processing image: {attachment.filename}")
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
                content_parts.append({
                    "type": "text",
                    "text": user_text
                })
            elif has_images:
                content_parts.append({
                    "type": "text",
                    "text": "Eksplike sa w wè nan screenshot sa a pou kont Amazon mwen an."
                })          

            # Get conversation history
            history = get_history(message.author.id)
            
            # Prepare messages for Claude
            messages = []
            for msg in history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Add current message
            messages.append({
                "role": "user",
                "content": content_parts
            })
            
            # Call Claude with Vision
            response = claude_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=3000,
                temperature=0.7,
                system="""Ou se WCA Bot, yon SPESYALIS EKSKLUSIF Amazon FBA/FBM ki pale Kreyòl Ayisyen.

🚨 RÈG ABSOLUTMAN ENPÒTAN:
- Ou SÈLMAN pale sou AMAZON SELLING - PA ANYEN LÒT.
- Si kesyon an pa klè oswa semble pa gen rapò ak Amazon, TOUJOU assume li sou Amazon.
- Ou PA KA bay konsèy sou: legal immigration, tribal law, general retail, lòt ecommerce platforms.
- CHAK REPONS OU DWE EKSPLIKE KIJAN SA FONKSYONE SOU AMAZON.

🎯 KESYON TIPIK OU REPONN:
- "Resi Walmart/Target mache?" -> Non! Resi retail pa bon pou ungate.
- "Removal order" -> Amazon FBA removal order sèlman.

PÈSONALITE:
- Pale Kreyòl natirèl, dwe dirèk, sèvi ak emoji 📦💰🎯.
- Ou PA janm soti nan Amazon context!""",
                messages=messages
            )
            
            # Get Claude's response
            assistant_message = response.content[0].text
            
            # Save to history
            add_to_history(message.author.id, "user", user_text or "[Image sent]", has_images)
            add_to_history(message.author.id, "assistant", assistant_message)
            
            # Send response
            if len(assistant_message) > 2000:
                chunks = [assistant_message[i:i+1900] for i in range(0, len(assistant_message), 1900)]
                for chunk in chunks:
                    await message.channel.send(chunk)
            else:
                await message.channel.send(assistant_message)
        
        except Exception as e:
            error_msg = f"❌ Dezole, gen yon pwoblèm. Erè: {str(e)}"
            await message.channel.send(error_msg)
            print(f"Error: {e}")
# ---- Commands ----

@bot.command(name="help")
async def help_command(ctx):
    """Montre tout kòmandman yo"""
    embed = discord.Embed(
        title="📚 WCA Bot - Kòmandman",
        description="Asistan Amazon FBA/FBM ak Vision! 👁️",
        color=discord.Color.blue()
    )
    

    embed.add_field(
        name="💬 Poze Kesyon",
        value="Jis ekri kesyon ou dirèkteman nan chat la!",
        inline=False
    )
    
    embed.add_field(
        name="📸 Vision Features",
        value="Upload screenshot epi:\n• Mande m eksplike sa w wè\n• Mande m idantifye pwoblèm\n• Mande m bay konsey\n\nEgzanp: Upload screenshot Seller Central epi tape:\n`Eksplike sa screenshot sa a montre`\n`Ki metrics ki pi enpòtan la?`\n`Gen pwoblèm?`",
        inline=False
    )
    
    embed.add_field(
        name="📋 Kòmandman Jeneral",
        value="`!help` - Montre mesaj sa a\n`!ping` - Check bot status\n`!stats` - Wè estatistik\n`!example` - Wè egzanp kesyon",
        inline=False
    )
    
    embed.set_footer(text="Bot kreye pa WCA | Powered by Claude Vision")
    
    await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping_command(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)
    
    embed = discord.Embed(
        title="🏓 Pong!",
        description="Bot la ap travay san pwoblèm!",
        color=discord.Color.green()
    )
    
    embed.add_field(name="⚡ Latency", value=f"{latency}ms", inline=True)
    embed.add_field(name="✅ Status", value="Online", inline=True)
    embed.add_field(name="👁️ Vision", value="Enabled", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name="stats")
async def stats_command(ctx):
    """Show bot statistics"""
    embed = discord.Embed(
        title="📊 WCA Bot Statistics",
        color=discord.Color.gold()
    )
    
    embed.add_field(name="🌐 Sèvè", value=str(len(bot.guilds)), inline=True)
    embed.add_field(name="👥 Itilizatè", value=str(len(bot.users)), inline=True)
    embed.add_field(name="⚡ Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="🧠 AI Model", value="Claude Sonnet 4", inline=True)
    embed.add_field(name="👁️ Vision", value="Enabled", inline=True)
    embed.add_field(name="💬 Konvèsasyon", value=str(len(conversation_history)), inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name="example")
async def example_command(ctx):
    """Show example questions"""
    examples = """
📝 **Egzanp Kesyon ou ka poze:**

**Sans Screenshot:**
• Ki jan pou m optimize title pwodui m?
• Kijan pou m jwenn bon keywords?
• Konbyen bullets mwen dwe itilize?

**Ak Screenshot:** 📸
• [Upload Seller Central] Eksplike sa dashboard sa a montre
• [Upload listing] Ki pwoblèm ou wè nan listing sa a?
• [Upload ads] Ki metrics ki pi enpòtan nan PPC campaign sa a?
• [Upload inventory] Gen stock issues?

Jis tape kesyon ou dirèkteman! 💬
Upload screenshot pou plis detay! 📸
"""
    await ctx.send(examples)

@bot.command(name="fees")
async def fees_command(ctx, price: float = 0):
    """Calculate Amazon fees"""
    if price <= 0:
        await ctx.send("❌ Itilizasyon: `!fees [pri]`\nEgzanp: `!fees 29.99`")
        return
    
    referral_fee = price * 0.15
    fba_fee = 3.50
    total_fees = referral_fee + fba_fee
    net_revenue = price - total_fees
    
    embed = discord.Embed(
        title="💰 Kalkilasyon Frè Amazon",
        color=discord.Color.gold()
    )
    
    embed.add_field(name="💵 Pri Vant", value=f"${price:.2f}", inline=True)
    embed.add_field(name="📊 Referral Fee (15%)", value=f"${referral_fee:.2f}", inline=True)
    embed.add_field(name="📦 FBA Fee (est.)", value=f"${fba_fee:.2f}", inline=True)
    embed.add_field(name="💸 Total Fees", value=f"${total_fees:.2f}", inline=True)
    embed.add_field(name="✅ Net Revenue", value=f"${net_revenue:.2f}", inline=True)
    
    embed.set_footer(text="⚠️ Sa se yon estimasyon. Check Seller Central pou frè egzak.")
    
    await ctx.send(embed=embed)

@bot.command(name="profit")
async def profit_command(ctx, price: float = 0, cost: float = 0):
    """Calculate profit"""
    if price <= 0 or cost <= 0:
        await ctx.send("❌ Itilizasyon: `!profit [pri] [kou]`\nEgzanp: `!profit 35 15`")
        return
    
    referral_fee = price * 0.15
    fba_fee = 3.50
    total_fees = referral_fee + fba_fee
    net_revenue = price - total_fees
    profit = net_revenue - cost
    margin = (profit / price) * 100 if price > 0 else 0
    
    embed = discord.Embed(
        title="📊 Kalkilasyon Profit",
        color=discord.Color.green() if profit > 0 else discord.Color.red()
    )
    
    embed.add_field(name="💵 Pri Vant", value=f"${price:.2f}", inline=True)
    embed.add_field(name="🛒 Kou Pwodui", value=f"${cost:.2f}", inline=True)
    embed.add_field(name="📉 Total Fees", value=f"${total_fees:.2f}", inline=True)
    embed.add_field(name="💰 Profit", value=f"${profit:.2f}", inline=True)
    embed.add_field(name="📈 Margin", value=f"{margin:.1f}%", inline=True)
    
    if margin >= 25:
        embed.add_field(name="✅ Evaluasyon", value="Bon profit margin!", inline=False)
    elif margin >= 15:
        embed.add_field(name="⚠️ Evaluasyon", value="Akseptab, men ka amelyore", inline=False)
    else:
        embed.add_field(name="❌ Evaluasyon", value="Margin twò ba!", inline=False)
    
    await ctx.send(embed=embed)

# ---- Run bot ----
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ DISCORD_TOKEN pa defini!")
        exit(1)
    
    if not os.getenv("CLAUDE_API_KEY"):
        print("❌ CLAUDE_API_KEY pa defini!")
        exit(1)
    
    print("🚀 WCA Bot ap kòmanse...")
    print("📦 Amazon Assistant powered by Claude Vision")
    print("👁️ Vision capabilities: ENABLED")
    bot.run(TOKEN)