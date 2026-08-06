import os
import json
import urllib.request
import asyncio
import discord

GIST_ID = os.environ.get("GIST_ID")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

def _load_data_sync():
    if not GITHUB_TOKEN or not GIST_ID:
        return {}
    
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "DiscordBot"
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            files = result.get("files", {})
            file_obj = files.get("user_data.json") or files.get("data.json")
            
            if file_obj and "content" in file_obj:
                content = file_obj["content"]
                return json.loads(content) if content.strip() else {}
            else:
                return {}
    except Exception:
        return {}

async def load_data():
    return await asyncio.to_thread(_load_data_sync)

def _save_data_sync(data):
    if not GITHUB_TOKEN or not GIST_ID:
        return

    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "DiscordBot"
    }
    payload = json.dumps({
        "files": {
            "user_data.json": {
                "content": json.dumps(data, ensure_ascii=False, indent=4)
            }
        }
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="PATCH")
        with urllib.request.urlopen(req):
            pass
    except Exception:
        pass

async def save_data(data):
    await asyncio.to_thread(_save_data_sync, data)

def _load_allowed_channels_sync():
    if not GITHUB_TOKEN or not GIST_ID:
        return {}
    
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "DiscordBot"
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            files = result.get("files", {})
            file_obj = files.get("channel_allow.json")
            if file_obj and "content" in file_obj:
                content = file_obj["content"]
                return json.loads(content) if content.strip() else {}
            else:
                return {}
    except Exception:
        return {}

async def load_allowed_channels(bot=None):
    data = await asyncio.to_thread(_load_allowed_channels_sync)
    
    # Nếu truyền bot vào, kiểm tra tính tồn tại của các kênh
    if bot and data:
        cleaned_data = {}
        has_deleted = False

        for cid_str, perms in list(data.items()):
            if not cid_str.isdigit():
                has_deleted = True
                continue

            cid = int(cid_str)
            channel = bot.get_channel(cid)
            if channel is None:
                try:
                    channel = await bot.fetch_channel(cid)
                except (discord.NotFound, discord.HTTPException):
                    channel = None

            if channel is not None:
                cleaned_data[cid_str] = perms
            else:
                has_deleted = True

        if has_deleted:
            await save_allowed_channels(cleaned_data)
            return cleaned_data

    return data

def _save_allowed_channels_sync(data):
    if not GITHUB_TOKEN or not GIST_ID:
        return

    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "DiscordBot"
    }
    
    payload = json.dumps({
        "files": {
            "channel_allow.json": {
                "content": json.dumps(data, ensure_ascii=False, indent=4)
            }
        }
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="PATCH")
        with urllib.request.urlopen(req):
            pass
    except Exception:
        pass

async def save_allowed_channels(data):
    await asyncio.to_thread(_save_allowed_channels_sync, data)

def get_streak_text(streak_days: int) -> str:
    if streak_days < 3:
        return f"🧊 {max(0, streak_days)} ngày"
    return f"🔥 {streak_days} ngày"

def format_points(points: int, shorten: bool = False) -> str:
    if shorten:
        if points >= 1_000_000:
            val = round(points / 1_000_000, 1)
            return f"{val:.1f}M".replace(".", ",") if val % 1 != 0 else f"{int(val)}M"
        elif points >= 1_000:
            val = round(points / 1_000, 1)
            return f"{val:.1f}k".replace(".", ",") if val % 1 != 0 else f"{int(val)}k"
        return str(points)
    return f"{points:,}".replace(",", ".")
    
