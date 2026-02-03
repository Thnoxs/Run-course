import sys
import asyncio
import os
import json
import uvicorn
import socket
import webbrowser
import threading
import time
from telethon import TelegramClient
from telethon.sessions import StringSession
from fastapi import FastAPI, Response, Request
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse
import re
from contextlib import asynccontextmanager

# --- PATH CONFIGURATION ---
BASE_DIR = os.path.expanduser("~/.course")
COURSES_FILE = os.path.join(BASE_DIR, "courses.json")
SESSION_FILE = os.path.join(BASE_DIR, "session.txt")

# --- GLOBAL VARIABLES ---
API_ID = None 
API_HASH = None
CHANNEL_INPUT = None

# --- GLOBAL STATE ---
CURRENT_PORT = 8000
client = None
target_entity = None
course_structure = {}

# --- HELPER: LOGGING ---
def log(msg):
    print(f"[TeloView] {msg}")

# --- HELPER: FIND FREE PORT ---
def get_free_port(start_port=8000):
    port = start_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(('localhost', port)) != 0:
                return port
            port += 1

# --- HELPER: AUTO OPEN BROWSER ---
def trigger_browser():
    # Uses global CURRENT_PORT to ensure correct link opens
    url = f"http://localhost:{CURRENT_PORT}"
    log(f"🚀 Opening Browser: {url}")
    webbrowser.open(url)

# --- HELPER: SEARCH COURSES ---
def load_and_search_courses(keyword):
    if not os.path.exists(COURSES_FILE): return []
    matches = []
    try:
        with open(COURSES_FILE, 'r') as f:
            data = json.load(f)
        keyword = keyword.lower()
        for key, info in data.items():
            search_text = f"{key} {info.get('title', '')} {info.get('author', '')}".lower()
            if keyword in search_text:
                matches.append((key, info))
    except Exception as e:
        log(f"❌ JSON Error: {e}")
    return matches

# --- HELPER: WIZARD ADD ---
def wizard_add_course():
    print("\n✨ --- ADD NEW COURSE --- ✨")
    default_id = "25721571"
    default_hash = "3e6762dc02d94f4737178552060f2b57"
    existing = {}
    
    if os.path.exists(COURSES_FILE):
        try:
            with open(COURSES_FILE, 'r') as f:
                existing = json.load(f)
                if existing:
                    first = next(iter(existing.values()))
                    default_id = first.get('api_id', default_id)
                    default_hash = first.get('api_hash', default_hash)
        except: pass

    short_name = input("🔹 Short ID: ").strip()
    if not short_name: return print("❌ ID Required!")
    
    title = input(f"🔹 Full Title: ").strip() or short_name
    author = input("🔹 Author: ").strip()
    link = input("🔹 Telegram Link: ").strip()
    
    if not link: return print("❌ Link Required!")

    print(f"\n🔑 Credentials (Enter to use defaults)")
    api_id = input(f"🔹 API ID: ").strip() or default_id
    api_hash = input(f"🔹 API Hash: ").strip() or default_hash

    existing[short_name] = {
        "title": title, "author": author, 
        "api_id": api_id, "api_hash": api_hash, 
        "channel_link": link
    }
    
    with open(COURSES_FILE, 'w') as f: json.dump(existing, f, indent=4)
    print(f"\n✅ Course '{title}' added! Try: play {short_name}\n")

# --- HELPER: LIST COURSES ---
def list_courses():
    if not os.path.exists(COURSES_FILE): return print("📭 No courses.")
    with open(COURSES_FILE) as f: data = json.load(f)
    print("\n📚 --- YOUR LIBRARY ---")
    print(f"{'ID':<20} | {'AUTHOR':<15} | {'TITLE'}")
    print("-" * 70)
    for k, v in data.items():
        print(f"{k:<20} | {v.get('author', 'N/A')[:15]:<15} | {v.get('title')[:40]}...")
    print("-" * 70 + "\n")

# --- HELPER: RESOLVE CHANNEL ---
async def resolve_channel(user_input):
    user_input = str(user_input).strip()
    if "web.telegram.org" in user_input:
        match = re.search(r'#(-?\d+)', user_input)
        if match: return int(match.group(1))
    if "t.me/c/" in user_input:
        parts = user_input.split("t.me/c/")
        if len(parts) > 1: return int(f"-100{parts[1].split('/')[0]}")
    if "t.me/" in user_input:
        return user_input.replace("https://t.me/", "").replace("t.me/", "").split("/")[0]
    if re.match(r'^-?\d+$', user_input):
        return int(user_input)
    return user_input

# --- HELPER: CLEAN TITLES ---
def clean_title(name):
    if not name: return "Untitled Lesson"
    name = re.sub(r'\.(mp4|mkv|mov|avi|webm)$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'@\w+\s*[-_|]?\s*', '', name)
    name = re.sub(r'^(Copy of|Forwarded)\s*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^[-_|\s]+', '', name)
    return name.strip()

# --- LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global target_entity, course_structure
    log("🚀 Server Starting...")
    if not client: sys.exit(1)

    await client.start()
    try:
        identifier = await resolve_channel(CHANNEL_INPUT)
        try:
            target_entity = await client.get_entity(identifier)
        except ValueError:
            async for dialog in client.iter_dialogs():
                if dialog.id == identifier or str(dialog.id).endswith(str(identifier).replace("-100", "")):
                    target_entity = dialog.entity
                    break
            if not target_entity: raise Exception("Channel not found!")

        channel_title = getattr(target_entity, 'title', 'Unknown Course')
        log(f"✅ Connected to: {channel_title}")
        
        all_msgs = []
        async for msg in client.iter_messages(target_entity, limit=None):
            if msg.media or (msg.message and "MODULE:" in msg.message.upper()):
                all_msgs.append(msg)
        all_msgs.reverse()

        current_module = "Course Content"
        course_structure = {current_module: []}
        
        for msg in all_msgs:
            if msg.message and not msg.media:
                text = msg.message.strip()
                if "MODULE:" in text.upper() or (len(text) < 60 and not text.startswith("http")):
                    clean_name = text.replace("MODULE:", "").replace("Module:", "").strip()
                    clean_name = re.sub(r'^[-_|\s]+', '', clean_name)
                    current_module = clean_name
                    if current_module not in course_structure: 
                        course_structure[current_module] = []
            
            elif msg.media and hasattr(msg, 'file'):
                is_video = False
                if hasattr(msg.file, 'mime_type') and msg.file.mime_type.startswith('video/'):
                    is_video = True
                
                if is_video:
                    raw_name = getattr(msg.file, 'name', None)
                    if not raw_name: raw_name = f"Lesson {msg.id}"
                    final_title = clean_title(raw_name)
                    course_structure[current_module].append({ "id": msg.id, "title": final_title })

        course_structure = {k: v for k, v in course_structure.items() if v}
        log(f"📚 Indexed {len(course_structure)} Sections.")
        
        # Trigger Browser AFTER Indexing is done
        threading.Thread(target=trigger_browser).start()
        
    except Exception as e:
        log(f"❌ Error: {e}")
    
    yield
    if client: await client.disconnect()

app = FastAPI(lifespan=lifespan)

# --- ROUTES ---
@app.get("/icon.png")
async def serve_icon_file():
    path = os.path.join(BASE_DIR, "icon.png")
    return FileResponse(path) if os.path.exists(path) else Response(status_code=404)

@app.get("/logo.png")
async def serve_logo_file():
    path = os.path.join(BASE_DIR, "logo.png")
    return FileResponse(path) if os.path.exists(path) else Response(status_code=404)

@app.get("/")
async def dashboard():
    sidebar_html = ""
    icon_circle = '<svg viewBox="0 0 24 24" class="icon icon-status"><path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z"></path></svg>'
    is_flat_course = (len(course_structure) == 1 and "Course Content" in course_structure)

    if is_flat_course:
        videos = course_structure["Course Content"]
        for vid in videos:
            sidebar_html += f'''
            <div class="lesson-item" id="lesson-{vid['id']}" data-id="{vid['id']}" onclick="loadVideo({vid['id']}, '{vid['title']}', this)">
                <div class="status-icon-wrapper" onclick="toggleCompletion(event, {vid['id']})">
                    {icon_circle}
                </div>
                <div class="lesson-content">
                    <span class="lesson-title">{vid['title']}</span>
                </div>
                <div class="progress-track"><div class="progress-fill" id="progress-{vid['id']}"></div></div>
            </div>'''
    else:
        for i, (module_name, videos) in enumerate(course_structure.items()):
            is_first = (i == 0)
            display_style = "block" if is_first else "none"
            header_class = "section-header" if is_first else "section-header collapsed"
            sidebar_html += f'''
            <div class="section-container" data-module-index="{i}">
                <div class="{header_class}" onclick="toggleSection(this)">
                    <div class="header-left"><span class="section-title">{module_name}</span></div>
                    <span class="arrow">▼</span>
                </div>
                <div class="section-videos" style="display: {display_style};">
            '''
            for vid in videos:
                sidebar_html += f'''
                <div class="lesson-item" id="lesson-{vid['id']}" data-id="{vid['id']}" onclick="loadVideo({vid['id']}, '{vid['title']}', this)">
                    <div class="status-icon-wrapper" onclick="toggleCompletion(event, {vid['id']})">
                        {icon_circle}
                    </div>
                    <div class="lesson-content">
                        <span class="lesson-title">{vid['title']}</span>
                    </div>
                    <div class="progress-track"><div class="progress-fill" id="progress-{vid['id']}"></div></div>
                </div>'''
            sidebar_html += "</div></div>"

    page_title = getattr(target_entity, 'title', 'TELO Player')
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{page_title}</title>
        <link rel="icon" type="image/png" href="/icon.png">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
        <link href="https://vjs.zencdn.net/7.20.3/video-js.css" rel="stylesheet" />
        <link href="https://unpkg.com/@videojs/themes@1.0.1/dist/city/index.css" rel="stylesheet">
        
        <style>
            :root {{ 
                --bg-main: #0a0a0a; 
                --bg-sidebar: #111111; 
                --bg-header: #111111; 
                --bg-hover: #1e1e1e; 
                --bg-active: #1f1f1f; 
                --text-primary: #ededed; 
                --text-secondary: #a0a0a0; 
                --accent: #3b82f6; 
                --border: 1px solid #262626; 
                --font-stack: 'Inter', sans-serif; 
            }}
            * {{ box-sizing: border-box; outline: none; -webkit-tap-highlight-color: transparent; }}
            ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
            ::-webkit-scrollbar-track {{ background: transparent; }}
            ::-webkit-scrollbar-thumb {{ background: #333; border-radius: 3px; }}
            
            body {{ 
                margin: 0; background: var(--bg-main); font-family: var(--font-stack); 
                color: var(--text-primary); display: flex; flex-direction: column; 
                height: 100vh; overflow: hidden; font-size: 14px;
            }}
            
            .navbar {{ 
                height: 60px; background: var(--bg-header); border-bottom: var(--border); 
                display: flex; align-items: center; justify-content: space-between; 
                padding: 0 24px; z-index: 50; flex-shrink: 0; 
            }}
            .brand {{ display: flex; align-items: center; gap: 12px; text-decoration: none; }}
            .brand img {{ width: 28px; height: 28px; filter: invert(1); }}
            .brand-text {{ font-weight: 800; font-size: 1.2rem; letter-spacing: 1px; color: #fff; }}
            .brand-course {{ font-weight: 400; color: #666; margin-left: 10px; font-size: 0.9rem; border-left: 1px solid #333; padding-left: 10px; }}
            
            .app-container {{ display: flex; flex: 1; overflow: hidden; }}
            
            #sidebar {{ 
                width: 350px; background: var(--bg-sidebar); display: flex; 
                flex-direction: column; border-right: var(--border); z-index: 40; 
                min-width: 250px; max-width: 500px; user-select: none;
            }}
            #curriculum {{ flex: 1; overflow-y: auto; overflow-x: hidden; position: relative; }}
            
            .footer {{ 
                font-size: 11px; color: #555; text-align: center; padding: 12px; 
                border-top: var(--border); background: var(--bg-sidebar); 
            }}
            
            .section-header {{ 
                padding: 16px 20px; cursor: pointer; display: flex; 
                justify-content: space-between; align-items: center; 
                background: var(--bg-sidebar); border-bottom: 1px solid #1a1a1a;
            }}
            .section-header:hover {{ background: var(--bg-hover); }}
            .section-title {{ font-weight: 600; font-size: 0.9rem; color: #e0e0e0; }}
            .arrow {{ font-size: 10px; color: #666; transition: transform 0.3s; }}
            .section-header.collapsed .arrow {{ transform: rotate(-90deg); }}
            
            .lesson-item {{ 
                padding: 12px 20px;
                cursor: pointer; display: flex; gap: 14px; 
                align-items: center;
                position: relative;
                background: #0f0f0f; transition: all 0.2s;
                border-bottom: 1px solid #161616;
                height: 50px;
            }}
            .lesson-item:hover {{ background: var(--bg-hover); }}
            .lesson-item.active {{ background: var(--bg-active); }}
            .lesson-item.active .lesson-title {{ color: var(--accent); font-weight: 500; }}
            
            .lesson-content {{
                flex: 1; min-width: 0; display: flex; align-items: center;
            }}

            .lesson-title {{ 
                font-size: 0.9rem; color: var(--text-secondary); 
                white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; width: 100%;
            }}
            
            .status-icon-wrapper {{ 
                width: 20px; min-width: 20px; 
                display: flex; justify-content: center; align-items: center; cursor: pointer; z-index: 10;
            }}
            .icon-status {{ width: 16px; height: 16px; color: #444; }}

            .progress-track {{ 
                position: absolute; bottom: 0; left: 0; width: 100%; height: 2px; 
                background: transparent; pointer-events: none;
            }}
            .progress-fill {{ height: 100%; background: var(--accent); width: 0%; transition: width 0.3s linear; box-shadow: 0 0 10px var(--accent); }}
            
            .video-js.vjs-user-inactive .vjs-control-bar {{ opacity: 1 !important; visibility: visible !important; display: flex !important; }}
            body.cinema .video-js.vjs-user-inactive .vjs-control-bar,
            .video-js.vjs-fullscreen.vjs-user-inactive .vjs-control-bar {{
                opacity: 0 !important; visibility: hidden !important;
                transition: visibility 1s, opacity 1s !important;
            }}
            
            .wave-container {{ display: flex; align-items: flex-end; justify-content: center; gap: 2px; height: 14px; width: 16px; }}
            .wave-bar {{ width: 3px; background: var(--accent); animation: wave-bounce 1s infinite ease-in-out; border-radius: 1px; }}
            .wave-bar:nth-child(1) {{ animation-delay: 0.0s; height: 40%; }}
            .wave-bar:nth-child(2) {{ animation-delay: 0.2s; height: 80%; }}
            .wave-bar:nth-child(3) {{ animation-delay: 0.4s; height: 50%; }}
            @keyframes wave-bounce {{ 0%, 100% {{ height: 30%; }} 50% {{ height: 100%; }} }}

            #main {{ flex: 1; display: flex; flex-direction: column; background: #000; position: relative; }}
            
            #video-header {{
               height: 45px; display: flex; align-items: center; justify-content: center; 
               background: #000; color: #fff; font-size: 0.95rem; font-weight: 500; 
               border-top: 1px solid #111; letter-spacing: 0.5px; text-align: center;  
               padding: 0 20px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
            }}
            
            .player-wrapper {{ flex: 1; width: 100%; display: flex; justify-content: center; align-items: center; background: #000; }}
            
            .control-bar {{ 
                height: 60px; display: none; align-items: center; justify-content: center; 
                gap: 16px; flex-shrink: 0; 
            }}
            .nav-btn {{ 
                background: #1f1f1f; border: 1px solid #333; color: #ccc; 
                padding: 8px 20px; border-radius: 6px; cursor: pointer; 
                transition: 0.2s; font-weight: 500; 
            }}
            .nav-btn:hover {{ background: #333; color: white; border-color: #555; }}
            
            #resizer {{ width: 4px; background: #111; cursor: col-resize; z-index: 55; border-left: 1px solid #222; }}
            #resizer:hover {{ background: var(--accent); }}
            
            body.cinema .navbar, body.cinema #sidebar, body.cinema #resizer, body.cinema #video-header {{ display: none; }}
            body.cinema #main {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 100; }}
            body.cinema .control-bar {{ 
                position: absolute; bottom: 0; width: 100%; 
                background: linear-gradient(to top, rgba(0,0,0,0.9), transparent); 
                border: none; opacity: 0; 
            }}
            body.cinema #main:hover .control-bar {{ opacity: 1; }}
        </style>
    </head>
    <body>
       <nav class="navbar">
            <a href="#" class="brand">
                <img src="/logo.png" onerror="this.src='/icon.png'; this.onerror=null;">
                <span class="brand-text">TELO</span>
                <span class="brand-course">{page_title}</span>
            </a>
            <div style="font-size: 0.8rem; color: #666;">{len(course_structure) if not is_flat_course else len(course_structure["Course Content"])} {("Modules" if not is_flat_course else "Videos")}</div>
        </nav>

        <div class="app-container">
            <div id="sidebar">
                <div id="curriculum">{sidebar_html}</div>
                <div class="footer">
                    Made with <span style="color:#e91e63;">&#10084;</span> by <b>Thnoxs</b>
                </div>
            </div>
            
            <div id="resizer"></div>
            <div id="main">
                <div class="player-wrapper">
                    <video id="vid" class="video-js vjs-big-play-centered" controls preload="auto"></video>
                </div>
                 
                <div class="control-bar">
                    <button class="nav-btn" onclick="playPrev()">Previous</button>
                    <button class="nav-btn" onclick="toggleCinema()">Theater Mode</button>
                    <button class="nav-btn" onclick="playNext()">Next</button>
                </div>
                 <div id="video-header">Select a video to start</div>
            </div>
        </div>
        
        <script src="https://vjs.zencdn.net/7.20.3/video.js"></script>
        <script>
            const ICON_CIRCLE = '<svg viewBox="0 0 24 24" class="icon icon-status"><path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z"></path></svg>';
            const ICON_CHECK = '<svg viewBox="0 0 24 24" class="icon icon-status"><path fill="#3b82f6" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"></path></svg>';
            const WAVE_HTML = `<div class="wave-container"><div class="wave-bar"></div><div class="wave-bar"></div><div class="wave-bar"></div></div>`;

            var player = videojs('vid', {{ fluid: false, fill: true, playbackRates: [0.75, 1, 1.25, 1.5, 2] }});
            var currentId = null;

            player.on('timeupdate', () => {{
                if(!currentId) return;
                const percent = (player.currentTime() / player.duration()) * 100;
                const progressBar = document.getElementById('progress-' + currentId);
                if(progressBar) progressBar.style.width = percent + '%';
            }});

            window.onload = function() {{ 
                const first = document.querySelector('.lesson-item'); 
                if(first) first.click(); 
            }};

            function loadVideo(id, title, element) {{
                if(currentId === id) {{ player.paused() ? player.play() : player.pause(); return; }}
                currentId = id; 

                document.querySelectorAll('.lesson-item').forEach(el => {{ 
                    el.classList.remove('active');
                    const prog = el.querySelector('.progress-fill');
                    const iconWrap = el.querySelector('.status-icon-wrapper');
                    if(prog.style.width !== '100%') iconWrap.innerHTML = ICON_CIRCLE;
                    else iconWrap.innerHTML = ICON_CHECK;
                }});
                
                element.classList.add('active'); 
                const iconWrap = element.querySelector('.status-icon-wrapper');
                if(element.querySelector('.progress-fill').style.width !== '100%') iconWrap.innerHTML = WAVE_HTML;

                document.getElementById('video-header').innerText = title;

                const parentSection = element.closest('.section-videos');
                if (parentSection) {{
                    document.querySelectorAll('.section-videos').forEach(sec => {{
                        if (sec !== parentSection) {{ sec.style.display = 'none'; sec.previousElementSibling.classList.add('collapsed'); }}
                    }});
                    parentSection.style.display = 'block'; parentSection.previousElementSibling.classList.remove('collapsed'); 
                }}

                player.src({{ src: '/stream/' + id, type: 'video/mp4' }}); 
                player.play();
            }}

            function toggleCompletion(e, id) {{
                e.stopPropagation();
                const el = document.getElementById('lesson-' + id);
                const iconWrap = el.querySelector('.status-icon-wrapper');
                const progress = el.querySelector('.progress-fill');
                
                if (progress.style.width === '100%') {{
                    progress.style.width = '0%';
                    iconWrap.innerHTML = (currentId === id) ? WAVE_HTML : ICON_CIRCLE;
                }} else {{
                    progress.style.width = '100%';
                    iconWrap.innerHTML = ICON_CHECK;
                }}
            }}

            player.on('ended', () => {{
                const el = document.getElementById('lesson-' + currentId);
                if(el) {{
                    el.querySelector('.status-icon-wrapper').innerHTML = ICON_CHECK;
                    el.querySelector('.progress-fill').style.width = '100%';
                }}
                playNext();
            }});

            function toggleSection(header) {{ 
                const content = header.nextElementSibling; 
                const isCollapsed = content.style.display === 'none'; 
                content.style.display = isCollapsed ? 'block' : 'none'; 
                header.classList.toggle('collapsed', !isCollapsed); 
            }}
            function getAllIds() {{ return Array.from(document.querySelectorAll('.lesson-item')).map(el => parseInt(el.getAttribute('data-id'))); }}
            function playNext() {{ 
                const ids = getAllIds(); 
                const next = ids[ids.indexOf(currentId) + 1]; 
                if (next) document.getElementById('lesson-'+next).click(); 
            }}
            function playPrev() {{ 
                const ids = getAllIds(); 
                const prev = ids[ids.indexOf(currentId) - 1]; 
                if (prev) document.getElementById('lesson-'+prev).click(); 
            }}
            function toggleCinema() {{ document.body.classList.toggle('cinema'); player.trigger('resize'); }}
            
            const resizer = document.getElementById('resizer');
            resizer.addEventListener('mousedown', (e) => {{
                e.preventDefault();
                document.addEventListener('mousemove', resize);
                document.addEventListener('mouseup', () => document.removeEventListener('mousemove', resize));
            }});
            function resize(e) {{
                if(e.clientX > 250 && e.clientX < 600) document.getElementById('sidebar').style.width = e.clientX + 'px';
            }}
            
            document.addEventListener('keydown', (e) => {{
                if (e.code === 'Space') {{ e.preventDefault(); player.paused() ? player.play() : player.pause(); }}
                if (e.key === 'ArrowRight') {{ if(e.metaKey) playNext(); else player.currentTime(player.currentTime() + 5); }}
                if (e.key === 'ArrowLeft') {{ if(e.metaKey) playPrev(); else player.currentTime(player.currentTime() - 5); }}
                if (e.key === 'f') toggleCinema();
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html_content)

# --- ROUTE: STREAMING ---
async def iter_file(msg_media, start_byte, total_to_send):
    bytes_sent = 0
    async for chunk in client.iter_download(msg_media, offset=start_byte, request_size=512*1024):
        if bytes_sent >= total_to_send: break
        left_to_send = total_to_send - bytes_sent
        chunk = chunk[:left_to_send] if len(chunk) > left_to_send else chunk
        yield chunk
        bytes_sent += len(chunk)

@app.get("/stream/{msg_id}")
async def stream_video(msg_id: int, request: Request):
    try:
        msg = await client.get_messages(target_entity, ids=msg_id)
        if not msg or not msg.media: return Response("Not Found", status_code=404)
        file_size = msg.file.size
        
        range_header = request.headers.get("Range")
        if range_header:
            byte_match = re.search(r"bytes=(\d+)-(\d*)", range_header)
            start = int(byte_match.group(1))
            end = int(byte_match.group(2)) if byte_match.group(2) else file_size - 1
            content_length = end - start + 1
            return StreamingResponse(
                iter_file(msg.media, start, content_length), 
                status_code=206, 
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}", 
                    "Accept-Ranges": "bytes", 
                    "Content-Length": str(content_length), 
                    "Content-Type": "video/mp4"
                }
            )
        return StreamingResponse(iter_file(msg.media, 0, file_size), media_type="video/mp4")
    except Exception as e:
        log(f"Stream Error: {e}")
        return Response("Error", status_code=500)

# --- CLI ENTRY POINT (UPDATED LOGIN LOGIC) ---
async def do_login(api_id=None, api_hash=None, phone=None):
    # Interactive Wizard Mode for Login
    if not api_id:
        api_id = input("🔹 Enter API ID: ").strip()
    if not api_hash:
        api_hash = input("🔹 Enter API Hash: ").strip()
    if not phone:
        phone = input("🔹 Enter Phone Number (with code): ").strip()

    temp_client = TelegramClient(StringSession(), int(api_id), api_hash)
    await temp_client.connect()
    
    if not await temp_client.is_user_authorized():
        print(f"📩 Sending OTP to {phone}...")
        await temp_client.send_code_request(phone)
        otp = input("🔑 Enter Telegram OTP: ").strip()
        await temp_client.sign_in(phone, otp)
    
    session_str = temp_client.session.save()
    with open(SESSION_FILE, "w") as f:
        f.write(session_str)
        
    print(f"\n✅ LOGIN SUCCESS! Session saved to {SESSION_FILE}")
    await temp_client.disconnect()

def run_engine():
    global client, API_ID, API_HASH, CHANNEL_INPUT, CURRENT_PORT
    if len(sys.argv) < 2: return
    
    cmd = sys.argv[1]
    
    # 1. LOGIN (Corrected)
    if cmd == "login":
        if len(sys.argv) >= 5:
            # Manual Mode: login <id> <hash> <phone>
            asyncio.run(do_login(sys.argv[2], sys.argv[3], sys.argv[4]))
        else:
            # Interactive Mode: just 'login'
            asyncio.run(do_login())
            
    # 2. LIST 
    elif cmd == "list":
        list_courses()

    # 3. ADD 
    elif cmd == "add":
        wizard_add_course()

    # 4. OPEN 
    elif cmd == "open":
        keyword = " ".join(sys.argv[2:]) 
        print(f"🔎 Searching for: '{keyword}'...")
        
        matches = load_and_search_courses(keyword)
        
        if not matches:
            print(f"❌ No courses found for '{keyword}'. Use 'course-add' to create one.")
            return
        
        selected = None
        if len(matches) > 1:
            print("\n🤔 Multiple courses found. Which one?")
            for i, (key, info) in enumerate(matches):
                print(f"   [{i+1}] {info.get('title')} (by {info.get('author')})")
            
            try:
                choice = input("\n👉 Enter number (1, 2...): ")
                idx = int(choice) - 1
                selected = matches[idx][1]
            except:
                print("❌ Invalid selection.")
                return
        else:
            selected = matches[0][1]

        print(f"\n🚀 Launching: {selected.get('title')}")
        API_ID = selected['api_id']
        API_HASH = selected['api_hash']
        CHANNEL_INPUT = selected['channel_link']
        
        if not os.path.exists(SESSION_FILE):
            print("❌ Session not found. Running login wizard...")
            asyncio.run(do_login())
            # Reload session after login
            if not os.path.exists(SESSION_FILE): return

        with open(SESSION_FILE) as f: sess = f.read().strip()
        client = TelegramClient(StringSession(sess), int(API_ID), API_HASH)
        
        # FIX: Update GLOBAL CURRENT_PORT
        CURRENT_PORT = get_free_port()
        print(f"🌐 Server starting on Port: {CURRENT_PORT}")
        uvicorn.run(app, host="0.0.0.0", port=CURRENT_PORT)

if __name__ == "__main__":
    run_engine()