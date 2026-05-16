import os
import shutil
import json
import numpy as np
import face_recognition
import traceback
import urllib.parse
import secrets
import stat
import gc
import time
import platform
import subprocess
import ftplib
import threading
import socket
import io
import sys
import getpass
import httpx
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from fastapi import Form, Depends
from datetime import datetime
from typing import List, Set, Optional
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont, ImageEnhance
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Header, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, HTMLResponse, StreamingResponse
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
import uvicorn
from linebot.v3.webhook import WebhookParser, WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, MulticastRequest, PushMessageRequest
from linebot.v3.messaging.models import ReplyMessageRequest, FlexMessage, TextMessage, ImageMessage, FlexContainer
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# ================= CONFIGURATION =================
# ⚠️ โดเมนจริง (HTTPS)
PUBLIC_BASE_URL = "https://multisnap.site" 

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"
SECRET_KEY = "super_secret_key_for_session"
FACE_TOLERANCE = 0.48 

# LOGIN CONFIG
GOOGLE_CLIENT_ID = "YOUR_GOOGLE_CLIENT_ID"
GOOGLE_CLIENT_SECRET = "YOUR_GOOGLE_CLIENT_SECRET"
LINE_LOGIN_CHANNEL_ID = "YOUR_LINE_LOGIN_ID"
LINE_LOGIN_CHANNEL_SECRET = "YOUR_LINE_LOGIN_SECRET"

app = FastAPI()
db_lock = threading.Lock() # 🚀 เพิ่มบรรทัดนี้เพื่อป้องกัน DB พัง

# ================= MIDDLEWARE =================
@app.middleware("http")
async def security_and_logging(request: Request, call_next):
    path = request.url.path
    
    # 1. Allow Static
    if path.startswith("/events_files"): 
        return await call_next(request)
    if path.startswith("/events_data"): 
        return await call_next(request)
    if path.startswith("/admin_assets"): 
        return await call_next(request)
    if path.startswith("/static"): 
        return await call_next(request)
    
    # 2. Public Routes
    public_routes = [
        "/login", "/api/login", "/auth", "/callback", "/gallery", "/api/photos", 
        "/api/search-face", "/api/scan-face", "/api/send-line", "/api/get-event", 
        "/api/get-line-settings", "/api/dashboard-stats", "/api/get-events", 
        "/api/upload", "/health", "/api/create-event", "/api/update-event", "/slideshow", 
        "/watermark-setting", "/cloud-settings", "/settings", "/line-oa", 
        "/create-event-page", "/edit-event-page", "/create_event", "/new-event",
        "/analytic", "/analytics", "/edit-event",
        "/api/register-alert", "/api/download", "/api/save-watermark", 
        "/api/get-watermark", "/api/upload-watermark", "/api/get-server-ip", 
        "/register_notification", "/api/register-notification", 
        "/api/get-connection-info", "/api/get-cloud-settings", 
        "/api/save-cloud-settings", "/api/delete-event", "/logout", "/favicon.ico",
        "/api/sync/upload", "/api/admin/generate-key"
    ]
    
    # 3. Allow DELETE
    if request.method == "DELETE":
        pass 
    elif not any(path.startswith(p) for p in public_routes) and path != "/":
        if not (path.startswith("/slideshow/") or path.startswith("/analytics/") or path.startswith("/gallery/") or path.startswith("/edit-event-page/")):
            user = request.session.get('user')
            if not user:
                return RedirectResponse(url="/login")
    
    response = await call_next(request)
    
    # 4. Cache Control
    if not path.startswith("/events_files"):
        if not path.startswith("/events_data"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    
    return response

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, https_only=True)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)
oauth = OAuth()
oauth.register(name='google', client_id=GOOGLE_CLIENT_ID, client_secret=GOOGLE_CLIENT_SECRET, server_metadata_url='https://accounts.google.com/.well-known/openid-configuration', client_kwargs={'scope': 'openid email profile'})

# ================= PATH SETUP =================
if getattr(sys, 'frozen', False): 
    APP_ROOT = sys._MEIPASS
    DATA_ROOT = os.path.dirname(sys.executable)
else: 
    APP_ROOT = os.path.dirname(os.path.abspath(__file__))
    DATA_ROOT = APP_ROOT

BASE_DIR = APP_ROOT
ADMIN_DIR = os.path.join(APP_ROOT, "admin")
FRONTEND_DIR = os.path.join(APP_ROOT, "frontend")
DATA_DIR = os.path.join(DATA_ROOT, "events_data")
WATERMARK_DIR = os.path.join(DATA_ROOT, "watermarks")
LINE_CONFIG_PATH = os.path.join(DATA_ROOT, "line_config.json")
WATERMARK_CONFIG_PATH = os.path.join(DATA_ROOT, "watermark_config.json")
CLOUD_CONFIG_PATH = os.path.join(DATA_ROOT, "cloud_config.json")
API_KEYS_PATH = os.path.join(DATA_ROOT, "api_keys.json")

for path in [DATA_DIR, WATERMARK_DIR]: 
    os.makedirs(path, exist_ok=True)

class LinePushPayload(BaseModel): 
    userId: str
    imageUrl: str

class WatermarkSettings(BaseModel): 
    event_id: str
    enabled: bool
    position: str = "bottom-right"
    opacity: int = 100
    scale: int = 20
    sizeMode: str = "prop"
    insetX: int = 0
    insetY: int = 0
    margin: int = 5

# ✅ UI RENDERER
def render_admin_page(filename: str):
    file_path = os.path.join(ADMIN_DIR, filename)
    if not os.path.exists(file_path): 
        return HTMLResponse(content=f"<h1>System Error</h1><p>File <b>{filename}</b> not found in /admin folder.</p>", status_code=404)
    
    content = ""
    with open(file_path, "r", encoding="utf-8") as f: 
        content = f.read()
    
    for part in ["sidebar", "header"]:
        p_path = os.path.join(ADMIN_DIR, f"{part}.html")
        if os.path.exists(p_path):
            with open(p_path, "r", encoding="utf-8") as f: 
                part_content = f.read()
                content = content.replace(f"<div id=\"{part}-placeholder\"></div>", part_content)
                content = content.replace(f"<div id=\"{part}-container\"></div>", part_content)
    
    if "layout.js" not in content: 
        content = content.replace("</body>", '<script src="/admin_assets/layout.js"></script>\n</body>')
    
    css_fix = """<style>#loading-overlay:not(.flex) { display: none !important; }</style>"""
    content = content.replace("</head>", css_fix + "</head>")
    return HTMLResponse(content=content)

def get_watermark_config(event_id):
    if os.path.exists(WATERMARK_CONFIG_PATH):
        try:
            with open(WATERMARK_CONFIG_PATH, 'r') as f: 
                return json.load(f).get(event_id, {"enabled": False})
        except: 
            pass
    return {"enabled": False}

def apply_watermark(image_path, event_id):
    config = get_watermark_config(event_id)
    if not config.get("enabled", False):
        return None
    wm_path = os.path.join(WATERMARK_DIR, f"{event_id}.png")
    if not os.path.exists(wm_path):
        return None
    try:
        base = Image.open(image_path).convert("RGBA")
        base = ImageOps.exif_transpose(base)
        wm = Image.open(wm_path).convert("RGBA")
        bw, bh = base.size
        ww, wh = wm.size
        scale = int(config.get("scale", 20)) / 100.0
        mode = config.get("sizeMode", "prop")
        nw, nh = ww, wh
        
        if mode == 'prop': 
            nw = int(bw * scale)
            nh = int(nw * (wh/ww))
        elif mode == 'fit': 
            r = min(bw/ww, bh/wh)
            nw = int(ww*r)
            nh = int(wh*r)
        elif mode == 'fill': 
            r = max(bw/ww, bh/wh)
            nw = int(ww*r)
            nh = int(wh*r)
            
        wm = wm.resize((nw, nh), Image.Resampling.LANCZOS)
        op = int(config.get("opacity", 100))
        if op < 100:
            alpha = wm.split()[3]
            alpha = ImageEnhance.Brightness(alpha).enhance(op/100.0)
            wm.putalpha(alpha)
            
        pos = config.get("position", "bottom-right")
        x = (bw - nw) // 2
        y = (bh - nh) // 2
        
        if "left" in pos: 
            x = 0
        elif "right" in pos: 
            x = bw - nw
        if "top" in pos: 
            y = 0
        elif "bottom" in pos: 
            y = bh - nh
            
        x += int(nw * (int(config.get("insetX", 0))/100.0))
        y += int(nh * (int(config.get("insetY", 0))/100.0))
        
        final = Image.new('RGBA', base.size, (0,0,0,0))
        final.paste(base, (0,0))
        final.paste(wm, (x, y), mask=wm)
        buf = io.BytesIO()
        final.convert("RGB").save(buf, 'JPEG', quality=95)
        buf.seek(0)
        return buf
    except: 
        return None

line_bot_api = None
parser = None
liff_id = ""
def load_line():
    global line_bot_api, parser, liff_id
    if os.path.exists(LINE_CONFIG_PATH):
        try:
            with open(LINE_CONFIG_PATH, 'r') as f:
                c = json.load(f)
                if c.get('access_token') and c.get('channel_secret'):
                    line_bot_api = MessagingApi(ApiClient(Configuration(access_token=c['access_token'])))
                    parser = WebhookParser(c['channel_secret'])
                    liff_id = c.get('liff_id', '')
                    print("✅ LINE OA Configured")
        except: 
            pass
load_line()

def create_flex(eid, name, date, cover_url):
    safe_eid = urllib.parse.quote(eid)
    base_url = PUBLIC_BASE_URL if PUBLIC_BASE_URL else "https://multisnap.site"
    uri = f"https://liff.line.me/{liff_id}?event={safe_eid}" if liff_id else f"{base_url}/gallery?event={safe_eid}"
    
    nocache_url = f"{cover_url}?v={int(time.time())}"
    
    return FlexMessage(alt_text=f"Event: {name}", contents=FlexContainer.from_dict({
        "type": "bubble",
        "hero": { 
            "type": "image", 
            "url": nocache_url, 
            "size": "full", 
            "aspectRatio": "20:13", 
            "aspectMode": "cover", 
            "action": { "type": "uri", "uri": uri }
        },
        "body": { 
            "type": "box", 
            "layout": "vertical", 
            "contents": [ 
                { "type": "text", "text": str(name), "weight": "bold", "size": "xl", "align": "center" }, 
                { "type": "text", "text": f"Date: {date}", "size": "sm", "color": "#aaaaaa", "align": "center" }
            ]
        },
        "footer": { 
            "type": "box", 
            "layout": "vertical", 
            "contents": [ 
                { "type": "button", "style": "primary", "color": "#10b981", "action": { "type": "uri", "label": "เปิดแกลลอรี่", "uri": uri }}
            ]
        }
    }))

app.mount("/admin_assets", StaticFiles(directory=ADMIN_DIR), name="admin_assets")
app.mount("/events_files", StaticFiles(directory=DATA_DIR), name="events_files")
app.mount("/events_data", StaticFiles(directory=DATA_DIR), name="events_data")

# ================= CLOUD SYNC LOGIC =================

def load_api_keys():
    if os.path.exists(API_KEYS_PATH):
        try:
            with open(API_KEYS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_api_keys(keys):
    with open(API_KEYS_PATH, "w", encoding="utf-8") as f:
        json.dump(keys, f, indent=4, ensure_ascii=False)

def verify_api_key(event_id: str, api_key: str):
    keys = load_api_keys()
    return keys.get(event_id) == api_key

# ================= ROUTES =================

@app.get("/")
async def index(): 
    return RedirectResponse("/dashboard")

@app.get("/login")
async def login_p(): 
    return render_admin_page("login.html")

@app.get("/dashboard")
async def dashboard_p(): 
    return render_admin_page("dashboard.html")

@app.get("/events")
async def events_p(): 
    return render_admin_page("events.html")

@app.get("/edit-event-page/{event_id}")
async def edit_event_page_route(event_id: str):
    return render_admin_page("edit_event.html")

@app.get("/event/upload/{event_id}")
@app.get("/tools/{event_id}")
async def upload_p(event_id: str): 
    return render_admin_page("tools.html")

# ✅ GALLERY
@app.get("/gallery")
async def gal_root(): 
    if os.path.exists(os.path.join(FRONTEND_DIR, "gallery.html")):
        return FileResponse(os.path.join(FRONTEND_DIR, "gallery.html"))
    return HTMLResponse("<h1>Gallery Not Found in /frontend</h1>", status_code=404)

@app.get("/gallery/{p:path}")
async def gal_sub(p: str): 
    if os.path.exists(os.path.join(FRONTEND_DIR, "gallery.html")):
        return FileResponse(os.path.join(FRONTEND_DIR, "gallery.html"))
    return HTMLResponse("<h1>Gallery Not Found in /frontend</h1>", status_code=404)

@app.get("/line-oa")
async def line_p(): 
    return render_admin_page("line_oa.html")

@app.get("/watermark-setting")
async def wm_p(): 
    return render_admin_page("watermark_setting.html")

@app.get("/cloud-settings")
async def cloud_p(): 
    return render_admin_page("cloud_settings.html")

@app.get("/create-event")
@app.get("/create-event-page")
@app.get("/create_event")
@app.get("/new-event")
async def create_event_page():
    if os.path.exists(os.path.join(ADMIN_DIR, "create_event.html")):
        return render_admin_page("create_event.html")
    return RedirectResponse("/events")

@app.get("/slideshow")
@app.get("/slideshow/{event_id}")
async def slideshow_p(event_id: Optional[str] = None): 
    if os.path.exists(os.path.join(FRONTEND_DIR, "slideshow.html")):
        return FileResponse(os.path.join(FRONTEND_DIR, "slideshow.html"))
    return HTMLResponse("<h1>Error: slideshow.html not found in /frontend folder</h1>", status_code=404)

@app.get("/analytic")
@app.get("/analytics")
@app.get("/analytics/{event_id}")
async def analytic_p(event_id: Optional[str] = None): 
    if os.path.exists(os.path.join(FRONTEND_DIR, "analytics.html")):
        return FileResponse(os.path.join(FRONTEND_DIR, "analytics.html"))
    if os.path.exists(os.path.join(ADMIN_DIR, "analytics.html")):
        return render_admin_page("analytics.html")
    return HTMLResponse("<h1>Error: analytics.html not found</h1>", status_code=404)

@app.get("/edit-event/{event_id}")
async def edit_event_p(event_id: str):
    if os.path.exists(os.path.join(ADMIN_DIR, "edit_event.html")):
        return render_admin_page("edit_event.html")
    if os.path.exists(os.path.join(ADMIN_DIR, "create_event.html")):
        return render_admin_page("create_event.html")
    return RedirectResponse("/events")

# ================= API =================

@app.post("/api/admin/generate-key")
async def api_generate_key(request: Request):
    user = request.session.get('user')
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    data = await request.json()
    event_id = data.get("event_id")
    if not event_id:
        raise HTTPException(status_code=400, detail="Missing Event ID")
    
    new_key = f"MS_{secrets.token_hex(12).upper()}"
    keys = load_api_keys()
    keys[event_id] = new_key
    save_api_keys(keys)
    
    return {"status": "success", "api_key": new_key}

@app.post("/api/sync/upload")
async def sync_upload_api(
    background_tasks: BackgroundTasks,
    x_event_id: str = Header(...),
    x_api_key: str = Header(...),
    file: UploadFile = File(...)
):
    if not verify_api_key(x_event_id, x_api_key):
        raise HTTPException(status_code=403, detail="Invalid API Key or Event ID")

    eid = os.path.basename(x_event_id)
    ep = os.path.join(DATA_DIR, eid)
    if not os.path.exists(ep):
        raise HTTPException(status_code=404, detail="Event folder not found")
    
    os.makedirs(ep, exist_ok=True)
    filename = file.filename
    fp = os.path.join(ep, filename)

    try:
        with open(fp, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {"status": "success", "message": f"Synced: {filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ FIXED: API สำหรับลบรูปภาพ (แก้ไขให้ลบไฟล์จริง + Thumbnail + DB)
@app.delete("/api/delete/{event_id}/{filename}")
async def delete_photo(event_id: str, filename: str):
    eid = urllib.parse.unquote(event_id)
    fname = urllib.parse.unquote(filename)
    ep = os.path.join(DATA_DIR, os.path.basename(eid))
    fp = os.path.join(ep, fname)
    tp = os.path.join(ep, "thumbnails", fname)
    
    # 1. ลบไฟล์ภาพหลัก
    if os.path.exists(fp):
        os.remove(fp)
    else:
        return JSONResponse({"status": "error", "message": f"File {fname} not found on server"}, 404)
    
    # 2. ลบไฟล์ Thumbnail (ถ้ามี)
    if os.path.exists(tp):
        os.remove(tp)
        
    # 3. ลบข้อมูล Face Encoding ออกจาก face_database.json
    db_path = os.path.join(ep, "face_database.json")
    if os.path.exists(db_path):
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                db = json.load(f)
            # กรองข้อมูลออก เอาเฉพาะที่ไม่ใช่ชื่อไฟล์นี้
            new_db = [entry for entry in db if entry.get("image_name") != fname]
            with open(db_path, "w", encoding="utf-8") as f:
                json.dump(new_db, f, indent=4)
        except Exception as e:
            print(f"Error updating database after delete: {e}")
            
    return {"status": "success", "message": "Deleted successfully"}

# ✅ FIX SEND LINE: ยิงตรงผ่าน API และเคลียร์ไฟล์ขยะอัตโนมัติ (ป้องการ Storage เต็ม)
@app.post("/api/send-line")
async def send_line_api(payload: LinePushPayload):
    token = ""
    if os.path.exists(LINE_CONFIG_PATH):
        try:
            with open(LINE_CONFIG_PATH, "r", encoding="utf-8") as f:
                c = json.load(f)
                token = c.get('access_token', '')
        except:
            pass
            
    if not token: 
        return JSONResponse({"status": "error", "message": "LINE API not configured"}, 500)
    if not payload.userId: 
        return JSONResponse({"status": "error", "message": "User ID not found"}, 400)
        
    raw_url = payload.imageUrl
    clean_path = urllib.parse.unquote(raw_url).split("events_files/")[-1] if "events_files/" in raw_url else raw_url.lstrip("/")
    parts = clean_path.split("/")
    
    temp_file_path = None # ตัวแปรเก็บที่อยู่ไฟล์ชั่วคราว
    
    if len(parts) >= 2:
        eid, fname = parts[0], parts[-1]
        source_file = os.path.join(DATA_DIR, eid, fname)
        wm_buf = apply_watermark(source_file, eid)
        if wm_buf:
            temp_dir = os.path.join(DATA_DIR, eid, "temp_line")
            os.makedirs(temp_dir, exist_ok=True)
            temp_fname = f"line_{int(time.time())}_{fname}"
            temp_file_path = os.path.join(temp_dir, temp_fname)
            
            with open(temp_file_path, "wb") as f: 
                f.write(wm_buf.read())
            final_image_url = f"{PUBLIC_BASE_URL}/events_files/{urllib.parse.quote(eid)}/temp_line/{urllib.parse.quote(temp_fname)}"
        else:
            final_image_url = f"{PUBLIC_BASE_URL}/events_files/{urllib.parse.quote(eid)}/{urllib.parse.quote(fname)}"
    else:
        final_image_url = raw_url
        
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
    body = {
        "to": payload.userId,
        "messages": [
            {
                "type": "image",
                "originalContentUrl": final_image_url,
                "previewImageUrl": final_image_url
            }
        ]
    }
    
    try:
        import requests
        res = requests.post('https://api.line.me/v2/bot/message/push', json=body, headers=headers)
        
        # 🚀 ส่วนที่เพิ่มใหม่: ตั้งเวลาลบไฟล์ชั่วคราวทิ้งหลังผ่านไป 60 วินาที (รอให้เซิร์ฟเวอร์ LINE ดึงรูปเสร็จก่อน)
        if temp_file_path and os.path.exists(temp_file_path):
            import threading
            def delete_temp():
                try:
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
                except: pass
            threading.Timer(60.0, delete_temp).start()
        # ---------------------------------------------------------
        
        if res.status_code == 200:
            return {"status": "success"}
        else:
            return JSONResponse({"status": "error", "message": res.text}, 500)
    except Exception as e: 
        return JSONResponse({"status": "error", "message": str(e)}, 500)

@app.post("/api/update-event")
async def update_event_api(
    request: Request,
    event_id: str = Form(...),
    event_name: str = Form(...),
    event_date: str = Form(...),
    event_status: Optional[str] = Form(None),
    description: Optional[str] = Form(""),
    popcard: Optional[UploadFile] = File(None)
):
    eid = urllib.parse.unquote(event_id)
    path = os.path.join(DATA_DIR, os.path.basename(eid))
    meta_path = os.path.join(path, "metadata.json")
    if not os.path.exists(path): return JSONResponse({"status": "error", "message": "Folder not found"}, 404)
    current_meta = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f: current_meta = json.load(f)
        except: pass
    current_meta.update({
        "event_name": event_name,
        "event_date": event_date,
        "event_status": event_status if event_status else current_meta.get("event_status", "Live"),
        "description": description,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    try:
        with open(meta_path, "w", encoding="utf-8") as f: json.dump(current_meta, f, ensure_ascii=False, indent=4)
        if popcard and popcard.filename:
            with open(os.path.join(path, "popcard.jpg"), "wb") as buffer: shutil.copyfileobj(popcard.file, buffer)
        return {"status": "success", "message": "Updated"}
    except Exception as e: return JSONResponse({"status": "error", "message": str(e)}, 500)

@app.get("/api/photos/{event_id}")
async def get_photos(event_id: str):
    eid = urllib.parse.unquote(event_id)
    eid = os.path.basename(eid)
    ep = os.path.join(DATA_DIR, eid)
    
    if not os.path.exists(ep): 
        return {"photos": []}
    
    photos = []
    files = sorted(os.listdir(ep), key=lambda x: os.path.getmtime(os.path.join(ep, x)), reverse=True)
    
    for f in files:
        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')) and f != 'popcard.jpg':
            safe_eid = urllib.parse.quote(eid)
            safe_f = urllib.parse.quote(f)
            photos.append({
                "name": f,
                "url": f"/events_files/{safe_eid}/{safe_f}"
            })
            
    return {"photos": photos}

@app.delete("/api/delete-event/{event_id}")
async def delete_event_folder(event_id: str):
    eid = urllib.parse.unquote(event_id)
    eid = os.path.basename(eid)
    ep = os.path.join(DATA_DIR, eid)
    
    if os.path.exists(ep):
        try:
            shutil.rmtree(ep)
            return {"status": "success", "message": "Event deleted"}
        except Exception as e:
            return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
    else:
        return JSONResponse({"status": "error", "message": "Event not found"}, status_code=404)

async def process_face_search(event_id: str, file: UploadFile):
    eid = urllib.parse.unquote(event_id)
    eid = os.path.basename(eid)
    ep = os.path.join(DATA_DIR, eid)
    if not os.path.exists(ep): 
        return {"results": []}
    try:
        user_img_data = await file.read()
        user_img = Image.open(io.BytesIO(user_img_data)).convert("RGB")
        user_img = ImageOps.exif_transpose(user_img)
        user_encs = face_recognition.face_encodings(np.array(user_img))
        
        if len(user_encs) == 0: 
            return {"results": []}
            
        user_enc = user_encs[0]
        found_photos = []
        db_path = os.path.join(ep, "face_database.json")
        
        if os.path.exists(db_path):
            with open(db_path, "r") as f: 
                db = json.load(f)
            for entry in db:
                try:
                    known_enc = np.array(entry["encoding"])
                    match = face_recognition.compare_faces([known_enc], user_enc, tolerance=FACE_TOLERANCE)[0]
                    if match:
                        safe_eid = urllib.parse.quote(eid)
                        safe_fname = urllib.parse.quote(entry["image_name"])
                        url = f"/events_files/{safe_eid}/{safe_fname}"
                        if url not in found_photos: 
                            found_photos.append(url)
                except: 
                    pass
        return {"results": found_photos}
    except: 
        return {"results": []}

@app.post("/api/search-face")
async def search_face_main(event_id: str = Form(...), file: UploadFile = File(...)): 
    return await process_face_search(event_id, file)

@app.post("/api/scan-face")
async def search_face_alias(event_id: str = Form(...), file: UploadFile = File(...)): 
    return await process_face_search(event_id, file)

@app.get("/api/upload/{event_id}")
async def upload_check(): return {"status": "ok"}

@app.post("/api/upload/{event_id}")
async def upload_api(event_id: str, background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    eid = urllib.parse.unquote(event_id)
    eid = os.path.basename(eid)
    ep = os.path.join(DATA_DIR, eid)
    os.makedirs(ep, exist_ok=True)
    thumb_p = os.path.join(ep, "thumbnails")
    os.makedirs(thumb_p, exist_ok=True)
    db_path = os.path.join(ep, "face_database.json")
    
    db = []
    if os.path.exists(db_path):
        try: 
            with open(db_path, "r") as f: 
                db = json.load(f)
        except: 
            pass
            
    count = 0
    uploaded_files_info = []
    
    for file in files:
        filename = file.filename
        fp = os.path.join(ep, filename)
        with open(fp, "wb") as b: 
            shutil.copyfileobj(file.file, b)
        try: 
            with Image.open(fp) as img: 
                img = ImageOps.exif_transpose(img)
                img.thumbnail((500, 500))
                img.save(os.path.join(thumb_p, filename), "JPEG")
        except: 
            pass
            
        try:
            image = Image.open(fp).convert("RGB")
            image = ImageOps.exif_transpose(image)
            image.thumbnail((1600, 1600))
            encs = face_recognition.face_encodings(np.array(image))
            for e in encs: 
                db.append({"image_name": filename, "encoding": e.tolist()})
        except: 
            pass
            
        safe_eid = urllib.parse.quote(eid)
        safe_fname = urllib.parse.quote(filename)
        file_url = f"/events_files/{safe_eid}/{safe_fname}"
        
        uploaded_files_info.append({
            "name": filename,
            "url": file_url
        })
        count += 1
        
    with open(db_path, "w") as f: 
        json.dump(db, f)
        
    if count > 0: 
        notify_list = [f["name"] for f in uploaded_files_info]
        background_tasks.add_task(check_and_notify_users, event_id, notify_list)
        
    return {"status": "success", "count": count, "files": uploaded_files_info}

@app.post("/api/login")
async def api_login(r: Request):
    d = await r.json()
    if d.get("username")==ADMIN_USERNAME and d.get("password")==ADMIN_PASSWORD: 
        r.session['user']='admin'
        return {"status":"success"}
    return JSONResponse({"status":"error"}, 401)

@app.get("/api/current-user")
async def curr_user(r: Request): return {"user": r.session.get('user'), "role": "admin"}

@app.get("/logout")
async def logout(r: Request): 
    r.session.clear()
    return RedirectResponse("/login")

@app.post("/api/create-event")
async def create_event(
    request: Request, 
    event_name: str = Form(...), 
    event_date: str = Form(...), 
    folder_name: str = Form(...), 
    popcard: Optional[UploadFile] = File(None) 
):
    current_user = request.session.get('user')
    if not current_user: raise HTTPException(status_code=401, detail="Unauthorized")
    
    eid = folder_name.strip()
    if not eid:
        eid = datetime.now().strftime("%Y%m%d%H%M%S")
        
    path = os.path.join(DATA_DIR, eid)
    os.makedirs(path, exist_ok=True)
    os.makedirs(os.path.join(path, "thumbnails"), exist_ok=True)
    
    if popcard: 
        with open(os.path.join(path, "popcard.jpg"), "wb") as buffer: 
            shutil.copyfileobj(popcard.file, buffer)
            
    metadata = {"event_id": eid, "owner": current_user, "event_name": event_name, "event_date": event_date, "folder_name": folder_name}
    
    with open(os.path.join(path, "metadata.json"), "w", encoding="utf-8") as f: 
        json.dump(metadata, f, ensure_ascii=False, indent=4)
        
    return {"status": "success", "event_id": eid}

@app.get("/api/get-events")
async def get_events(request: Request):
    session_user = request.session.get('user')
    current_user = session_user if session_user else 'admin'
    
    evs = []
    if os.path.exists(DATA_DIR):
        for f in os.listdir(DATA_DIR):
            ep = os.path.join(DATA_DIR, f)
            if os.path.isdir(ep):
                m = os.path.join(ep, "metadata.json")
                if os.path.exists(m):
                    try:
                        with open(m, "r", encoding="utf-8") as file:
                            data = json.load(file)
                            if current_user == 'admin' or data.get("owner") == current_user:
                                if "event_name" not in data and "name" in data:
                                    data["event_name"] = data["name"]
                                data["event_id"] = f 
                                evs.append(data)
                    except Exception as e:
                        print(f"Error reading metadata in {f}: {e}")
    
    return {"events": evs}

@app.get("/api/get-connection-info/{event_id}")
async def get_connection_info(event_id: str):
    try: 
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except: 
        local_ip = "127.0.0.1"
    return { "ip": local_ip, "username": getpass.getuser(), "path": os.path.abspath(os.path.join(DATA_DIR, event_id)), "event_id": event_id }

@app.get("/api/get-event/{event_id}")
async def get_event(event_id: str):
    eid = urllib.parse.unquote(event_id)
    path = os.path.join(DATA_DIR, eid, "metadata.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f: 
            data = json.load(f)
        if "event_name" not in data and "name" in data: data["event_name"] = data["name"]
        return data
    raise HTTPException(status_code=404, detail="Event not found")

@app.post("/api/save-watermark")
async def save_watermark(settings: WatermarkSettings):
    all_config = {}
    if os.path.exists(WATERMARK_CONFIG_PATH):
        try: 
            with open(WATERMARK_CONFIG_PATH, 'r') as f: 
                all_config = json.load(f)
        except: 
            pass
            
    all_config[settings.event_id] = settings.dict()
    with open(WATERMARK_CONFIG_PATH, 'w') as f: 
        json.dump(all_config, f, indent=4)
        
    return {"status": "success"}

@app.post("/api/upload-watermark/{event_id}")
async def upload_watermark(event_id: str, file: UploadFile = File(...)):
    try: 
        path = os.path.join(WATERMARK_DIR, f"{event_id}.png")
        with open(path, "wb") as buffer: 
            shutil.copyfileobj(file.file, buffer)
        return {"status": "success"}
    except Exception as e: 
        return JSONResponse(status_code=500, content={"message": str(e)})

@app.get("/api/get-watermark/{event_id}")
async def get_watermark(event_id: str): 
    config = get_watermark_config(event_id)
    has_file = os.path.exists(os.path.join(WATERMARK_DIR, f"{event_id}.png"))
    return {"config": config, "has_file": has_file}

@app.get("/api/download/{event_id}/{filename}")
async def download_image(event_id: str, filename: str):
    eid = urllib.parse.unquote(event_id)
    fname = urllib.parse.unquote(filename)
    file_path = os.path.join(DATA_DIR, eid, fname)
    if not os.path.exists(file_path): 
        raise HTTPException(status_code=404, detail="File not found")
        
    watermarked = apply_watermark(file_path, eid)
    if watermarked: 
        return StreamingResponse(watermarked, media_type="image/jpeg")
    else: 
        return FileResponse(file_path)

@app.post("/api/register-notification")
async def register_notification(event_id: str = Form(...), user_id: str = Form(...), file: UploadFile = File(...)):
    try:
        eid = urllib.parse.unquote(event_id)
        register_dir = os.path.join(DATA_DIR, eid, "registered_faces")
        os.makedirs(register_dir, exist_ok=True)
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data)).convert("RGB")
        
        # 🚀 เพิ่มบรรทัดนี้: แก้ปัญหาภาพตะแคงจากมือถือ (EXIF Rotation) ให้ AI สแกนหน้าตรงได้
        image = ImageOps.exif_transpose(image)
        
        encodings = face_recognition.face_encodings(np.array(image))
        if len(encodings) > 0: 
            np.save(os.path.join(register_dir, f"{user_id}.npy"), encodings[0])
            return {"status": "success", "message": "บันทึกใบหน้าเรียบร้อย!"}
        else: 
            return {"status": "error", "message": "ไม่พบใบหน้าในรูป กรุณาถ่ายใหม่"}
    except Exception as e: 
        return {"status": "error", "message": str(e)}

# ================= ระบบแจ้งเตือนแบบรวมยอด (Batch Notification) =================
notification_queue = {}
notify_timer = None
notify_lock = threading.Lock()

def send_batched_notifications(force_user_id=None):
    global notify_timer
    with notify_lock:
        # ถ้าระบุ user_id (กรณีครบ 10 รูป) ให้ส่งแค่คนนั้น ถ้าไม่ระบุ ให้ส่งทุกคนที่รออยู่
        users_to_notify = [force_user_id] if force_user_id else list(notification_queue.keys())
        
        for user_id in users_to_notify:
            if user_id not in notification_queue:
                continue
                
            data = notification_queue[user_id]
            count = data['count']
            event_name = data['event_name']
            uri = data['uri']

            # ส่งแค่ข้อความ ไม่ส่งรูปภาพ เพื่อไม่ให้แชทรกรุงรัง
            msg_text = f"✨ เจอรูปของคุณมาใหม่ {count} รูปในงาน {event_name} ครับ!\n\nกดดูรูปได้ที่นี่เลย 👇\n{uri}"
            
            try:
                line_bot_api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[TextMessage(text=msg_text)]
                    )
                )
                print(f"✅ [LINE] ส่งแจ้งเตือนรวมยอด {count} รูป ให้แขกสำเร็จ!")
            except Exception as e:
                print(f"❌ [LINE Error] ส่งแจ้งเตือนไม่สำเร็จ: {e}")
            
            # เคลียร์คนที่ส่งแล้วออกจากตะกร้า
            del notification_queue[user_id]
        
        # ถ้าไม่มีใครรอคิวแล้ว ให้รีเซ็ตนาฬิกา
        if not notification_queue:
            if notify_timer is not None:
                notify_timer.cancel()
                notify_timer = None

def check_and_notify_users(event_id: str, new_files: List[str]):
    global notify_timer
    if not line_bot_api: return
    eid = urllib.parse.unquote(event_id)
    register_dir = os.path.join(DATA_DIR, eid, "registered_faces")
    ep = os.path.join(DATA_DIR, eid)
    if not os.path.exists(register_dir): return
    
    if not hasattr(check_and_notify_users, "notified_cache"): 
        check_and_notify_users.notified_cache = set()
        
    try: 
        with open(os.path.join(ep, "metadata.json"), "r") as f: 
            meta = json.load(f)
        event_name = meta.get("event_name", "Event")
    except: 
        event_name = "Event"
        
    base_url = PUBLIC_BASE_URL.rstrip("/") if PUBLIC_BASE_URL else "https://multisnap.site"
    uri = f"https://liff.line.me/{liff_id}?event={event_id}" if liff_id else f"{base_url}/gallery?event={event_id}"
    
    for filename in new_files:
        try:
            image = Image.open(os.path.join(ep, filename)).convert("RGB")
            image = ImageOps.exif_transpose(image)
            image.thumbnail((1600, 1600))
            img_array = np.array(image)
            unknown_encs = face_recognition.face_encodings(img_array)
            if len(unknown_encs) > 0:
                for reg_file in os.listdir(register_dir):
                    if reg_file.endswith(".npy"):
                        user_id = reg_file.replace(".npy", "")
                        
                        # ป้องกันการส่งแจ้งเตือนรูปเดิมซ้ำ
                        if f"{user_id}_{filename}" in check_and_notify_users.notified_cache: continue
                        
                        try:
                            known_enc = np.load(os.path.join(register_dir, reg_file))
                            if True in face_recognition.compare_faces(unknown_encs, known_enc, tolerance=FACE_TOLERANCE): 
                                check_and_notify_users.notified_cache.add(f"{user_id}_{filename}")
                                
                                with notify_lock:
                                    if user_id not in notification_queue:
                                        notification_queue[user_id] = {'count': 0, 'event_name': event_name, 'uri': uri}
                                    notification_queue[user_id]['count'] += 1
                                    
                                    current_count = notification_queue[user_id]['count']
                                    print(f"📥 นำรูปเข้าตะกร้ารอส่งให้แขก... (ตอนนี้มี {current_count} รูป)")
                                    
                                    # 🚀 เงื่อนไขที่ 1: ถ้าสแกนเจอครบ 10 รูปเมื่อไหร่ ให้ "ส่งทันที" ไม่ต้องรอเวลา
                                    if current_count >= 10:
                                        print(f"🎯 ครบ 10 รูป! ส่งแจ้งเตือนเข้า LINE ทันที")
                                        threading.Thread(target=send_batched_notifications, args=(user_id,)).start()
                                    
                                    # 🚀 เงื่อนไขที่ 2: ถ้ายังไม่ถึง 10 รูป ให้ตั้งเวลาเผื่อไว้ 90 วินาที
                                    elif notify_timer is None:
                                        print("⏳ เริ่มจับเวลา 90 วินาที หากไม่มีรูปมาเพิ่มจะส่งแจ้งเตือนทันที...")
                                        notify_timer = threading.Timer(90.0, send_batched_notifications)
                                        notify_timer.start()
                        except: 
                            continue
            del image, img_array, unknown_encs
            gc.collect()
        except: 
            pass

@app.post("/api/save-line-settings")
async def save_line_settings(request: Request):
    data = await request.json()
    with open(LINE_CONFIG_PATH, "w", encoding="utf-8") as f: 
        json.dump(data, f, indent=4)
    load_line()
    return {"status": "success"}

@app.get("/api/get-line-settings")
async def get_line_settings():
    if os.path.exists(LINE_CONFIG_PATH): 
        with open(LINE_CONFIG_PATH, "r", encoding="utf-8") as f: 
            return json.load(f)
    return {}

@app.post("/api/save-cloud-settings")
async def save_cloud_settings(request: Request):
    data = await request.json()
    with open(CLOUD_CONFIG_PATH, "w", encoding="utf-8") as f: 
        json.dump(data, f, indent=4)
    return {"status": "success"}

@app.get("/api/get-cloud-settings")
async def get_cloud_settings():
    if os.path.exists(CLOUD_CONFIG_PATH):
        with open(CLOUD_CONFIG_PATH, "r", encoding="utf-8") as f: 
            return json.load(f)
    return {}

@app.post("/callback")
async def callback(request: Request, x_line_signature: str = Header(None)):
    if not parser: return JSONResponse(status_code=500, content={"message": "No Config"})
    body = await request.body()
    body_str = body.decode("utf-8")
    try:
        events = parser.parse(body_str, x_line_signature)
        for event in events:
            if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
                text = event.message.text.strip()
                if text.startswith("view_event_"):
                    eid = text.replace("view_event_", "")
                    eid = urllib.parse.unquote(eid)
                    
                    meta_path = os.path.join(DATA_DIR, eid, "metadata.json")
                    if os.path.exists(meta_path):
                        with open(meta_path, "r", encoding="utf-8") as f: 
                            meta = json.load(f)
                        
                        try: 
                            flex = create_flex(eid, meta.get("event_name"), meta.get("event_date"), f"{PUBLIC_BASE_URL}/events_files/{urllib.parse.quote(eid)}/popcard.jpg")
                            line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[flex]))
                        except Exception as e: 
                            print(f"Line Error: {e}")
                            pass
    except InvalidSignatureError: 
        raise HTTPException(status_code=400, detail="Invalid signature")
    return "OK"

@app.get("/api/dashboard-stats")
async def get_dashboard_stats(request: Request):
    user = request.session.get('user')
    if not user: return JSONResponse({"status": "error"}, status_code=401)
    total_events, total_images, storage_used = 0, 0, 0
    if os.path.exists(DATA_DIR):
        for f in os.listdir(DATA_DIR):
            ep = os.path.join(DATA_DIR, f)
            if os.path.isdir(ep):
                m = os.path.join(ep, "metadata.json")
                if os.path.exists(m):
                    try:
                        with open(m, "r") as meta:
                            if json.load(meta).get("owner") == user or user == 'admin':
                                total_events += 1
                                for img in os.listdir(ep):
                                    if img.lower().endswith(('.jpg', '.png')): 
                                        total_images += 1
                                        storage_used += os.path.getsize(os.path.join(ep, img))
                    except: pass
    return {"events": total_events, "photos": total_images, "storage": storage_used}

@app.get('/login/google')
async def login_google(request: Request):
    if not GOOGLE_CLIENT_ID or "ใส่_GOOGLE" in GOOGLE_CLIENT_ID: return HTMLResponse("<h1>Error: Google Client ID not configured</h1>")
    return await oauth.google.authorize_redirect(request, f"{PUBLIC_BASE_URL}/auth/google")

@app.get('/auth/google')
async def auth_google(request: Request):
    try: 
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')
        request.session['user'] = user_info.get('email')
        return RedirectResponse(url='/dashboard')
    except Exception as e: 
        return HTMLResponse(f"<h1>Auth Error</h1><p>{str(e)}</p>")

@app.get('/login/line')
async def login_line():
    if not LINE_LOGIN_CHANNEL_ID or "ใส่_LINE" in LINE_LOGIN_CHANNEL_ID: return HTMLResponse("<h1>Error: LINE Channel ID not configured</h1>")
    state = secrets.token_urlsafe(16)
    return RedirectResponse(f"https://access.line.me/oauth2/v2.1/authorize?response_type=code&client_id={LINE_LOGIN_CHANNEL_ID}&redirect_uri={PUBLIC_BASE_URL}/auth/line&state={state}&scope=profile%20openid%20email")

@app.get('/auth/line')
async def auth_line(request: Request, code: str, state: str):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post("https://api.line.me/oauth2/v2.1/token", headers={'Content-Type': 'application/x-www-form-urlencoded'}, data={'grant_type': 'authorization_code', 'code': code, 'redirect_uri': f"{PUBLIC_BASE_URL}/auth/line", 'client_id': LINE_LOGIN_CHANNEL_ID, 'client_secret': LINE_LOGIN_CHANNEL_SECRET})
            token_data = resp.json()
            if 'id_token' not in token_data: return HTMLResponse(f"<h1>LINE Login Failed</h1><p>{token_data}</p>")
            verify_resp = await client.post("https://api.line.me/oauth2/v2.1/verify", data={'id_token': token_data['id_token'], 'client_id': LINE_LOGIN_CHANNEL_ID})
            user_info = verify_resp.json()
            request.session['user'] = user_info.get('email') or user_info.get('sub')
            return RedirectResponse(url='/dashboard')
    except Exception as e: 
        return HTMLResponse(f"<h1>Auth Error</h1><p>{str(e)}</p>")

@app.get("/health")
async def health(): return {"status": "ok"}

@app.get("/api/get-server-ip")
async def get_server_ip(): 
    try: 
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except: 
        return "127.0.0.1"

class NewPhotoHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(('.jpg', '.jpeg', '.png')):
            time.sleep(2) 
            
            file_path = event.src_path
            path_parts = Path(file_path).parts
            
            if "events_data" in path_parts:
                idx = path_parts.index("events_data")
                if len(path_parts) > idx + 1:
                    eid = path_parts[idx+1]
                    filename = path_parts[idx+2] if len(path_parts) > idx + 2 else path_parts[idx+1]
                    
                    if filename == "face_database.json" or "thumbnails" in path_parts or filename == "popcard.jpg" or "registered_faces" in path_parts:
                        return

                    print(f"✨ New Photo Detected via Sync: {filename} in {eid}")
                    threading.Thread(target=self.process_sync_photo, args=(eid, filename)).start()

    def process_sync_photo(self, eid, filename):
        try:
            ep = os.path.join(DATA_DIR, eid)
            fp = os.path.join(ep, filename)
            thumb_p = os.path.join(ep, "thumbnails")
            os.makedirs(thumb_p, exist_ok=True)
            
            with Image.open(fp) as img:
                img = ImageOps.exif_transpose(img)
                img.thumbnail((500, 500))
                img.save(os.path.join(thumb_p, filename), "JPEG")
            
            db_path = os.path.join(ep, "face_database.json")
            
            image = Image.open(fp).convert("RGB")
            image = ImageOps.exif_transpose(image)
            image.thumbnail((1600, 1600))
            encs = face_recognition.face_encodings(np.array(image))
            
            # 🚀 ครอบบล็อกนี้ด้วยบัตรคิว (Lock) เพื่อให้มันจัดคิวเขียนข้อมูลลงไฟล์ JSON ทีละรูป ไม่แย่งกัน
            with db_lock:
                db = []
                if os.path.exists(db_path):
                    with open(db_path, "r") as f: db = json.load(f)
                
                for e in encs:
                    db.append({"image_name": filename, "encoding": e.tolist()})
                
                with open(db_path, "w") as f:
                    json.dump(db, f)
            # -------------------------------------------------------------
            
            check_and_notify_users(eid, [filename])
            
            print(f"✅ Auto-Processed: {filename}")
        except Exception as e:
            print(f"❌ Error Auto-Processing {filename}: {e}")

def start_watcher():
    observer = Observer()
    handler = NewPhotoHandler()
    observer.schedule(handler, DATA_DIR, recursive=True)
    observer.start()
    print(f"👀 Watcher started on {DATA_DIR}")

if __name__ == "__main__":
    start_watcher()
    uvicorn.run(app, host="0.0.0.0", port=8000)