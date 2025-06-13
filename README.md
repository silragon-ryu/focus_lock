# 🔒 Silragon Focus Lock

**Silragon Focus Lock** is a powerful desktop application built with Python and PyQt5 that helps you enter deep work mode by eliminating distractions. It integrates with **SumatraPDF** and **Spotify**, blocks system shortcuts, hides the taskbar, and creates a fully immersive focus session to supercharge your productivity.

---

## ✨ Features

* **📄 PDF Focus Mode**
  Opens your selected PDF in **full-screen mode** via SumatraPDF (Windows only) for distraction-free reading or studying.

* **🎵 Spotify Integration**
  Automatically launches **Spotify** alongside your PDF for background music—without needing to switch apps.

* **🚫 Aggressive Shortcut Blocking**
  Blocks common interrupting shortcuts like `Alt+Tab`, `Win`, `Ctrl`, `Esc`, and `F11` during focus sessions.

* **🖥️ Taskbar & Start Menu Hiding** (Windows only)
  Completely hides the Windows taskbar and Start button while in session for a cleaner, distraction-free desktop.

* **🎧 F5 Spotify Shortcut**
  Press `F5` to instantly bring Spotify to the foreground if it loses focus.

* **⏲️ Session Timer**
  Set custom focus durations. The remaining time is always visible to keep you on track.

* **🔐 Session Lockdown**
  The app resists early termination. Attempts to close it mid-session will prompt a confirmation to maintain focus integrity.

---

## 🚀 Installation

### Prerequisites

* Python 3.6+
* [SumatraPDF](https://www.sumatrapdfreader.org/free-pdf-reader) (Windows only)
* Spotify Desktop App

### Dependencies

Install the required Python libraries:

```bash
pip install PyQt5 pygetwindow keyboard
```

### Setup

1. **Clone the Repository:**

```bash
git clone https://github.com/your-username/silragon-focus-lock.git
cd silragon-focus-lock
```

> Replace `your-username` with your actual GitHub username.

2. **(Optional) Create a Virtual Environment:**

```bash
python -m venv .venv
source .venv/Scripts/activate     # On Windows
# source .venv/bin/activate       # On macOS/Linux
```

3. **Place Icon File:**
   Ensure `dragon_icon.png` is in the same directory as `main.py` for the application icon to appear correctly.

---

## 🏃‍♂️ Usage

1. Run the application:

```bash
python main.py
```

2. In the GUI:

   * Click **Select PDF** and choose a document.
   * Set your desired focus session duration.
   * Click **Initiate Focus Lock 🔒**.

3. Once initiated:

   * The main window will hide.
   * SumatraPDF will open the PDF in full screen.
   * Spotify will launch automatically.
   * Keyboard shortcuts and taskbar will be disabled.

4. During session:

   * Stay focused on your PDF.
   * Press `F5` to bring Spotify to the front.
   * Attempting to switch apps will redirect focus back.

5. Ending the session:

   * The timer will automatically end the lock session.
   * Alternatively, attempting to close the app will prompt for confirmation.
   * After ending, system shortcuts and taskbar are restored.

---

## ⚠️ Notes & Troubleshooting

* **Windows-Only Features:**
  Taskbar hiding and full-screen PDF functionality work only on Windows.

* **SumatraPDF Path:**
  The app looks for SumatraPDF in standard install locations. If yours is custom, adjust the path in `get_sumatra_path()`.

* **Spotify Path:**
  Similar to above—custom installs may require editing `get_spotify_path()` in the source code.

* **Bypass Protection:**
  While the lockdown is strict, advanced users may still bypass it depending on their system privileges.

* **Console Window:**
  On Windows, the console is hidden when the GUI starts for a seamless experience.

---

## 🤝 Contributing

Contributions are welcome and appreciated!
If you find bugs, want to request a feature, or contribute code, feel free to:

* Open an [Issue](https://github.com/your-username/silragon-focus-lock/issues)
* Submit a [Pull Request](https://github.com/your-username/silragon-focus-lock/pulls)

Let’s build the ultimate focus tool together.

