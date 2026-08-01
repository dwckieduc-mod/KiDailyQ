import os
import json
import urllib.request

GIST_ID = os.environ.get("GIST_ID")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

def load_data():
    if not GITHUB_TOKEN or not GIST_ID:
        print("⚠️ Thiếu GITHUB_TOKEN hoặc GIST_ID trong Environment Variables!")
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
            content = result["files"]["user_data.json"]["content"]
            return json.loads(content)
    except Exception as e:
        print(f"❌ Lỗi khi đọc dữ liệu từ Gist: {e}")
        return {}

def save_data(data):
    if not GITHUB_TOKEN or not GIST_ID:
        print("⚠️ Không thể lưu: Thiếu GITHUB_TOKEN hoặc GIST_ID!")
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
        with urllib.request.urlopen(req) as response:
            pass
    except Exception as e:
        print(f"❌ Lỗi khi lưu dữ liệu lên Gist: {e}")

def get_streak_text(streak: int) -> str:
    """Trả về định dạng hiển thị Streak: >=3 ngày 🔥, <3 ngày ❄️"""
    if streak >= 3:
        return f"{streak} ngày 🔥"
    return f"{streak} ngày ❄️"
