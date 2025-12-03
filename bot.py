import discord
from discord.ext import commands
from discord import app_commands
import datetime
import os

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

log_channels = {}

CHANNEL_TYPES_RU = {
    discord.ChannelType.text: "Текстовый канал",
    discord.ChannelType.voice: "Голосовой канал",
    discord.ChannelType.category: "Категория",
    discord.ChannelType.forum: "Форум",
    discord.ChannelType.news: "Новостной канал",
    discord.ChannelType.stage_voice: "Сцена",
    discord.ChannelType.public_thread: "Публичная ветка",
    discord.ChannelType.private_thread: "Приватная ветка",
}

async def log_event(guild: discord.Guild, title: str, description: str, color=0x00ff00):
    channel_id = log_channels.get(guild.id)
    if channel_id:
        channel = guild.get_channel(channel_id)
        if channel:
            embed = discord.Embed(
                title=title,
                description=description,
                color=color,
                timestamp=datetime.datetime.utcnow()
            )
            await channel.send(embed=embed)
    os.makedirs("logs", exist_ok=True)
    file_path = f"logs/logs_{guild.id}.txt"
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.utcnow()}] {title}: {description}\n")

@bot.tree.command(name="setlog", description="Установить канал для логов")
@app_commands.describe(channel="Канал для логов")
async def setlog(interaction: discord.Interaction, channel: discord.TextChannel):
    log_channels[interaction.guild.id] = channel.id
    await interaction.response.send_message(f"✅ Канал для логов установлен: {channel.mention}", ephemeral=True)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Бот запущен как {bot.user}")

# ----------------- МЕМБЕРЫ -----------------
@bot.event
async def on_member_join(member):
    await log_event(member.guild, "Вход на сервер", f"{member.mention} вошёл на сервер", 0x00ff00)

@bot.event
async def on_member_update(before, after):
    # Тайм-аут
    if before.timed_out_until != after.timed_out_until:
        executor = None
        async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_update):
            if entry.target.id == after.id:
                executor = entry.user
                break
        if after.timed_out_until:
            text = f"{after.mention} помещён в тайм-аут до {after.timed_out_until}"
            if executor:
                text += f"\nИсполнитель: {executor.mention}"
            await log_event(after.guild, "Тайм-аут (Mute)", text, 0xffff00)
        else:
            text = f"{after.mention} снят с тайм-аута"
            await log_event(after.guild, "Тайм-аут завершён", text, 0x00ff00)
    
    # Никнейм
    if before.display_name != after.display_name:
        await log_event(after.guild, "Никнейм изменён", f"{before.display_name} → {after.display_name} ({after.mention})", 0xffff00)
    
    # Аватар
    if before.avatar != after.avatar:
        await log_event(after.guild, "Аватар изменён", f"{after.mention}", 0xffff00)
    
    # Роли
    if before.roles != after.roles:
        before_roles = ", ".join([r.name for r in before.roles if r.name != "@everyone"])
        after_roles = ", ".join([r.name for r in after.roles if r.name != "@everyone"])
        await log_event(after.guild, "Роли изменены", f"{after.mention}: {before_roles} → {after_roles}", 0xffff00)

@bot.event
async def on_member_remove(member):
    executor = None
    async for entry in member.guild.audit_logs(limit=5, action=discord.AuditLogAction.kick):
        if entry.target.id == member.id:
            executor = entry.user
            break
    if executor:
        text = f"{member.mention} был кикнут\nИсполнитель: {executor.mention}"
        await log_event(member.guild, "Кик пользователя", text, 0xff8800)
    else:
        text = f"{member.mention} покинул сервер"
        await log_event(member.guild, "Выход с сервера", text, 0xff0000)

@bot.event
async def on_member_ban(guild, user):
    executor = None
    reason = None
    async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
        if entry.target.id == user.id:
            executor = entry.user
            reason = entry.reason
            break
    text = f"{user.mention} был забанен"
    if executor:
        text += f"\nИсполнитель: {executor.mention}"
    if reason:
        text += f"\nПричина: {reason}"
    await log_event(guild, "Бан пользователя", text, 0xff0000)

@bot.event
async def on_member_unban(guild, user):
    text = f"{user.mention} был разбанен"
    await log_event(guild, "Разбан пользователя", text, 0x00ff00)

# ----------------- СООБЩЕНИЯ -----------------
@bot.event
async def on_message_delete(message):
    if message.author.bot: return
    deleter = None
    async for entry in message.guild.audit_logs(limit=5, action=discord.AuditLogAction.message_delete):
        if entry.target.id == message.author.id:
            deleter = entry.user
            break
    author_roles = ", ".join([r.name for r in message.author.roles if r.name != "@everyone"])
    text = f"Автор: {message.author} ({author_roles})\nСодержание: {message.content}"
    if deleter:
        text += f"\nУдалил: {deleter}"
    await log_event(message.guild, "Сообщение удалено", text, 0xff0000)

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content: return
    author_roles = ", ".join([r.name for r in before.author.roles if r.name != "@everyone"])
    text = f"Автор: {before.author} ({author_roles})\nСтарое: {before.content}\nНовое: {after.content}"
    await log_event(before.guild, "Сообщение изменено", text, 0xffff00)

@bot.event
async def on_bulk_message_delete(messages):
    guild = messages[0].guild
    await log_event(guild, "Массовое удаление сообщений", f"Удалено сообщений: {len(messages)}", 0xff0000)

# ----------------- КАНАЛЫ -----------------
@bot.event
async def on_guild_channel_create(channel):
    ch_type = CHANNEL_TYPES_RU.get(channel.type, str(channel.type))
    await log_event(channel.guild, "Канал создан", f"{ch_type}: {channel.name}", 0x00ff00)

@bot.event
async def on_guild_channel_delete(channel):
    ch_type = CHANNEL_TYPES_RU.get(channel.type, str(channel.type))
    deleter = None
    async for entry in channel.guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
        if entry.target.id == channel.id:
            deleter = entry.user
            break
    text = f"{ch_type}: {channel.name}"
    if deleter:
        text += f"\nУдалил: {deleter}"
    await log_event(channel.guild, "Канал удалён", text, 0xff0000)

@bot.event
async def on_guild_channel_update(before, after):
    ch_type = CHANNEL_TYPES_RU.get(after.type, str(after.type))
    await log_event(after.guild, "Канал изменён", f"{ch_type}: {before.name} → {after.name}", 0xffff00)

# ----------------- РОЛИ -----------------
@bot.event
async def on_guild_role_create(role):
    await log_event(role.guild, "Роль создана", f"{role.name}", 0x00ff00)

@bot.event
async def on_guild_role_delete(role):
    await log_event(role.guild, "Роль удалена", f"{role.name}", 0xff0000)

@bot.event
async def on_guild_role_update(before, after):
    await log_event(after.guild, "Роль изменена", f"{before.name} → {after.name}", 0xffff00)

# ----------------- ЭМОДЗИ И СТИКЕРЫ -----------------
@bot.event
async def on_guild_emojis_update(guild, before, after):
    await log_event(guild, "Эмодзи изменены", f"До: {len(before)}, После: {len(after)}", 0xffff00)

@bot.event
async def on_guild_stickers_update(guild, before, after):
    await log_event(guild, "Стикеры изменены", f"До: {len(before)}, После: {len(after)}", 0xffff00)

# ----------------- РЕАКЦИИ -----------------
@bot.event
async def on_reaction_add(reaction, user):
    await log_event(reaction.message.guild, "Реакция добавлена", f"{user} → {reaction.emoji} на сообщении {reaction.message.id}", 0x00ff00)

@bot.event
async def on_reaction_remove(reaction, user):
    await log_event(reaction.message.guild, "Реакция удалена", f"{user} → {reaction.emoji} на сообщении {reaction.message.id}", 0xff0000)

# ----------------- ГОЛОС -----------------
@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel != after.channel:
        await log_event(member.guild, "Голосовое состояние", f"{member}: {before.channel} → {after.channel}", 0xffff00)
