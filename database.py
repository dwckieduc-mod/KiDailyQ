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
            files = result.get("files", {})
            
            # 💡 Tự động linh hoạt nhận diện data.json hoặc user_data.json
            file_obj = files.get("user_data.json") or files.get("data.json")
            
            if file_obj and "content" in file_obj:
                content = file_obj["content"]
                return json.loads(content) if content.strip() else {}
            else:
                print("⚠️ Không tìm thấy file data.json hoặc user_data.json trên Gist!")
                return {}
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
    
    # Lưu vào user_data.json
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
    
