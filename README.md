**TELO** is a powerful, automated Telegram-based course streaming engine.  
It converts educational content from Telegram channels into a clean, Netflix-style dashboard with a built-in video player and progress tracking.

---

## ✨ Features

- **Smart Search** – Instantly find courses by keywords or author names
- **Auto-Indexing** – Automatically converts Telegram channel content into structured modules and lessons
- **Conflict Resolver** – If multiple courses share the same name, the engine asks you to choose
- **Wizard Mode** – Add new courses directly from the terminal without editing any JSON files
- **Multi-Server Support** – Run multiple courses simultaneously on different ports
- **Auto-Open** – Opens the localhost dashboard automatically after indexing is complete

---

## 🛠️ Quick Setup (One-Line Install)

Copy and paste the commands below into your terminal:

```bash
# 1. Clone the repository
git clone git@github.com:Thnoxs/Run-course.git

# 2. Enter the project directory
cd Run-course && code .

# 3. Run the auto-installer
chmod +x install.sh && ./install.sh

# 4. Apply environment settings
source ~/.zshrc
```

## 🚀 How to Use

After setup, you can use these commands from anywhere in your terminal:

1.  Login (First Time Only)
    _Log in using your Telegram credentials:_

```bash
telo-login
```

2. Add a Course
   _Add a new Telegram channel as a course:_

```bash
add
```

3. View Your Library
   _List all added courses:_

```bash
 list
```

4. Play a Course
   _Open a course using its name or any keyword:_

```bash
play {Your course name or just ENTER}
```

# Project Structure

- ~/.course/ – Stores all configuration and session files

- main.py – Core logic and streaming engine

- courses.json – Database of saved courses

- install.sh – Auto-installation script that sets up shortcuts

## ⚠️ Requirements
* Python 3.10+

* Telegram API ID & Hash (get them from my.telegram.org)

* FastAPI & Telethon (installed automatically by the installer)

---

<p align="center">Developed with ❤️ by Thnoxs</p>