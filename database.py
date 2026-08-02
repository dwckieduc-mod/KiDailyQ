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

def get_streak_text(streak_days: int) -> str:
    if streak_days <= 0:
        return "Chưa có streak"
    elif streak_days == 1:
        return "🔥 1 ngày"
    else:
        return f"🔥 {streak_days} ngày liên tiếp"

def format_points(points: int, shorten: bool = False) -> str:
    """
    Định dạng số điểm KiPoints:
    - shorten=False: 100580  -> "100.580"
    - shorten=True:  100580  -> "100,6k"
                     1250000 -> "1,3M"
    """
    if shorten:
        if points >= 1_000_000:
            val = round(points / 1_000_000, 1)
            return f"{val:.1f}M".replace(".", ",") if val % 1 != 0 else f"{int(val)}M"
        elif points >= 1_000:
            val = round(points / 1_000, 1)
            return f"{val:.1f}k".replace(".", ",") if val % 1 != 0 else f"{int(val)}k"
        return str(points)

    # Định dạng phân cách hàng nghìn bằng dấu chấm (VD: 100.580)
    return f"{points:,}".replace(",", ".")
    
