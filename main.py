import sys
import os
import subprocess
import time
import threading
import pygetwindow as gw
import keyboard
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QVBoxLayout,
    QFileDialog, QComboBox, QMessageBox, QHBoxLayout, QSizePolicy, QFrame
)
from PyQt5.QtCore import QTimer, Qt, QSize
from PyQt5.QtGui import QIcon, QPixmap
import ctypes

# Constants for ShowWindow (Windows API)
SW_HIDE = 0
SW_SHOW = 5

class ZenFocus(QWidget):
    """
    A PyQt5 application designed to help users focus by locking them into
    a PDF viewer and Spotify, while blocking common system shortcuts.
    This version includes taskbar hiding and an F6 shortcut for Spotify.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Silragon Focus Lock")
        self.setFixedSize(680, 380) # Increased fixed size slightly to accommodate header
        self.setWindowIcon(self.load_icon("dragon_icon.png"))

        self.pdf_path = None
        self.duration_minutes = 45
        self.end_time = None
        self.session_active = False

        self.spotify_window_ref = None # Reference to the Spotify window object
        self.f6_hotkey_id = None      # ID for the F6 hotkey hook

        # Apply the new stylesheet
        self.setStyleSheet(self.get_stylesheet())

        self.init_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer)

    def load_icon(self, filename):
        """
        Loads an application icon from the specified filename.
        Warns if the file is not found.
        """
        if os.path.exists(filename):
            return QIcon(filename)
        else:
            print(f"Warning: Icon file '{filename}' not found. Using default icon.")
            return QIcon()

    def get_stylesheet(self):
        """
        Returns the stylesheet with the modified navy color scheme
        and subtle accents.
        """
        return """
        QWidget {
            background-color: #0E1A3C;  /* Darker Navy Blue */
            color: #E0EBF5;             /* Light Grayish Blue */
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 15px;
        }
        QFrame#mainFrame { /* Main container for better grouping */
            background-color: #1A2E50; /* Slightly lighter shade for content area */
            border-radius: 15px;
            padding: 25px;
            margin: 15px; /* Margin around the central frame */
            border: 1px solid #3F51B5; /* Accent border */
        }

        QLabel#titleLabel {
            font-size: 32px;
            font-weight: bold;
            color: #90CAF9; /* Light Blue */
            margin-bottom: 5px;
            letter-spacing: 1px;
        }
        QLabel#subtitleLabel {
            font-size: 13px;
            color: #B0BEC5; /* Muted Blue-Gray */
            margin-bottom: 20px;
            font-style: italic;
        }
        QLabel { /* General QLabel styling for other labels */
            font-size: 15px;
            color: #E0EBF5;
        }
        QLabel#fileLabel { /* Specific style for selected file path */
            font-size: 14px;
            color: #BBDEFB;
            padding: 8px 10px;
            border: 1px solid #3F51B5;
            border-radius: 8px;
            background-color: #0B1630; /* Very dark background for input */
            min-height: 35px;
            qproperty-alignment: AlignLeft | AlignVCenter;
        }
        QLabel#timerLabel {
            font-size: 24px;
            font-weight: bold;
            color: #81C784; /* Green for timer */
            margin-top: 15px;
            letter-spacing: 1.5px;
        }
        QLabel#statusMessageLabel {
            font-size: 14px;
            color: #CFD8DC;
            margin-top: 5px;
            min-height: 20px;
        }

        QPushButton {
            background-color: #2196F3; /* Bright Blue */
            color: white;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
            padding: 10px 20px;
            border: none;
            min-width: 120px;
        }
        QPushButton:hover {
            background-color: #1976D2; /* Darker Blue on hover */
        }
        QPushButton:pressed {
            background-color: #1565C0; /* Even darker on press */
        }
        QPushButton#selectPdfButton { /* Separate style for Select PDF button */
            background-color: #64B5F6; /* Lighter Blue */
            color: white;
            padding: 8px 15px;
            font-size: 14px;
            border-radius: 8px;
            border: 1px solid #3F51B5;
        }
        QPushButton#selectPdfButton:hover {
            background-color: #42A5F5;
        }
        QComboBox {
            background-color: #E3F2FD; /* Very Light Blue */
            color: #212121; /* Dark text for contrast */
            border: 1px solid #90CAF9;
            border-radius: 5px;
            padding: 5px 10px;
            font-size: 14px;
            min-height: 30px;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left-width: 1px;
            border-left-color: #90CAF9;
            border-left-style: solid;
            border-top-right-radius: 5px;
            border-bottom-right-radius: 5px;
        }
        QComboBox::down-arrow {
            image: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAhElEQVR42mNkGDsgAWMYGBgY/f///4Hw39+/L+BhYGDg4B+IgXgQGZiB+C0YGNjAAYgZEwQGwQJmZhgYmBgiBsbAYGAEIGYAYyG2AEJgYsLAD/I8cEAAJkZlYGBgYWBg/k/wFwMDAwMDzP7gA+Z/YGNgYGJmYGBgYAApBQAALxZ6g1Uv4wMAAAAASUVORK5CYII=);
            width: 14px;
            height: 14px;
        }
        QComboBox QAbstractItemView {
            background-color: #E3F2FD;
            selection-background-color: #90CAF9;
            color: #212121;
            font-size: 14px;
            border: 1px solid #90CAF9;
            border-radius: 5px;
        }
        """

    def init_ui(self):
        """Initializes the user interface elements and their layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0) # No margins for the main window

        main_frame = QFrame(self) # Use a QFrame for the main content area
        main_frame.setObjectName("mainFrame")
        frame_layout = QVBoxLayout(main_frame)
        frame_layout.setContentsMargins(25, 25, 25, 25) # Padding inside the frame
        frame_layout.setSpacing(15) # Consistent spacing between elements

        # --- Header Section (Logo beside Title) ---
        header_layout = QHBoxLayout()
        
        # Dragon Icon
        dragon_icon_label = QLabel(self)
        pixmap = QPixmap('dragon_icon.png')
        if pixmap.isNull():
            print("Warning: 'dragon_icon.png' not found or invalid. No icon displayed.")
        else:
            pixmap = pixmap.scaled(58, 58, Qt.KeepAspectRatio, Qt.SmoothTransformation) # Scale for header
            dragon_icon_label.setPixmap(pixmap)
        dragon_icon_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        dragon_icon_label.setFixedSize(QSize(58, 58))

        # Title Label
        self.title = QLabel("Silragon Ryu Focus Lock")
        self.title.setObjectName("titleLabel")
        self.title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        header_layout.addWidget(dragon_icon_label)
        header_layout.addSpacing(10) # Space between icon and title
        header_layout.addWidget(self.title)
        header_layout.addStretch() # Pushes icon/title to the left

        frame_layout.addLayout(header_layout)

        # Subtitle
        self.subtitle = QLabel("Harness calm power, focus like a dragon.")
        self.subtitle.setObjectName("subtitleLabel")
        self.subtitle.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(self.subtitle)


        # File selection section
        file_layout = QHBoxLayout()
        self.file_label = QLabel("No PDF selected")
        self.file_label.setObjectName("fileLabel") # Assign object name for specific styling
        self.file_label.setWordWrap(True)
        self.file_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        file_layout.addWidget(self.file_label)

        self.select_btn = QPushButton("Select PDF")
        self.select_btn.setObjectName("selectPdfButton") # Assign object name for specific styling
        self.select_btn.clicked.connect(self.select_pdf)
        file_layout.addWidget(self.select_btn)
        frame_layout.addLayout(file_layout)

        # Duration selection section
        duration_layout = QHBoxLayout()
        duration_label = QLabel("Duration (minutes):")
        duration_layout.addWidget(duration_label)

        self.duration_combo = QComboBox()
        self.duration_combo.addItems(["15", "25", "30", "45", "60", "90", "120"])
        self.duration_combo.setCurrentText("25")
        duration_layout.addWidget(self.duration_combo)
        duration_layout.addStretch()
        frame_layout.addLayout(duration_layout)

        # Start button
        self.start_btn = QPushButton("Initiate Focus Lock 🔒")
        self.start_btn.clicked.connect(self.start_focus)
        self.start_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed) # Make it expand
        frame_layout.addWidget(self.start_btn)

        # Timer display
        self.timer_label = QLabel("Time Remaining: --:--:--")
        self.timer_label.setObjectName("timerLabel") # Assign object name for specific styling
        self.timer_label.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(self.timer_label)
        
        # Status message label
        self.status_message_label = QLabel("Ready for Focus.")
        self.status_message_label.setObjectName("statusMessageLabel") # Assign object name for specific styling
        self.status_message_label.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(self.status_message_label)

        frame_layout.addStretch() # Push content to top

        main_layout.addWidget(main_frame) # Add the frame to the main window layout

    def select_pdf(self):
        """Opens a file dialog for PDF selection and updates the display label."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select PDF File", "", "PDF Files (*.pdf)")
        if file_path:
            self.pdf_path = file_path
            # Truncate long file paths for better display
            display_path = os.path.basename(file_path)
            if len(display_path) > 30: # Adjust truncation length for smaller window
                display_path = "..." + display_path[-27:]
            self.file_label.setText(f"Selected: {display_path}")
            self.status_message_label.setText("PDF selected. Ready to lock focus.")
            self.status_message_label.setStyleSheet("color: #4CAF50;") # Green for success
        else:
            self.status_message_label.setText("PDF selection cancelled.")
            self.status_message_label.setStyleSheet("color: #FF5252;") # Red for warning

    def _hide_taskbar(self):
        """Hides the Windows taskbar and Start button."""
        if sys.platform.startswith('win'):
            try:
                taskbar_hwnd = ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None)
                if taskbar_hwnd:
                    ctypes.windll.user32.ShowWindow(taskbar_hwnd, SW_HIDE)
                    print("Taskbar hidden successfully.")
                else:
                    print("Taskbar window not found.")

                start_button_hwnd = ctypes.windll.user32.FindWindowW("Button", "Start")
                if start_button_hwnd:
                    ctypes.windll.user32.ShowWindow(start_button_hwnd, SW_HIDE)
                    print("Start button hidden successfully.")
                else:
                    print("Start button window not found.")

            except Exception as e:
                print(f"Error hiding taskbar: {e}")

    def _show_taskbar(self):
        """Shows the Windows taskbar and Start button."""
        if sys.platform.startswith('win'):
            try:
                taskbar_hwnd = ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None)
                if taskbar_hwnd:
                    ctypes.windll.user32.ShowWindow(taskbar_hwnd, SW_SHOW)
                    print("Taskbar shown successfully.")
                else:
                    print("Taskbar window not found for showing.")

                start_button_hwnd = ctypes.windll.user32.FindWindowW("Button", "Start")
                if start_button_hwnd:
                    ctypes.windll.user32.ShowWindow(start_button_hwnd, SW_SHOW)
                    print("Start button shown successfully.")
                else:
                    print("Start button window not found for showing.")
            except Exception as e:
                print(f"Error showing taskbar: {e}")

    def activate_spotify_hotkey_callback(self):
        """Callback function for the F6 hotkey to activate Spotify."""
        if self.session_active and self.spotify_window_ref and isinstance(self.spotify_window_ref, gw.Win32Window):
            try:
                if self.spotify_window_ref.isMinimized:
                    self.spotify_window_ref.restore()
                self.spotify_window_ref.activate()
                self.spotify_window_ref.raise_()
                print("F6 pressed: Activated Spotify.")
            except Exception as e:
                print(f"Error activating Spotify via F6: {e}")
        else:
            print("F6 pressed, but Spotify window not found or session not active.")

    def start_focus(self):
        """Initiates the focus lock session."""
        if not self.pdf_path:
            QMessageBox.warning(self, "Error", "Please select a PDF file first.")
            return

        self.duration_minutes = int(self.duration_combo.currentText())
        self.end_time = time.time() + self.duration_minutes * 60
        self.session_active = True

        # Hide the main UI window and set window flags
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.showMinimized()
        self.setVisible(False) # Hide the window completely

        # Disable UI controls during the session
        self.start_btn.setEnabled(False)
        self.select_btn.setEnabled(False)
        self.duration_combo.setEnabled(False)
        
        # Update status message before starting thread
        self.status_message_label.setText("Focus session active. Please do not close programs manually.")
        self.status_message_label.setStyleSheet("color: #FFC107;") # Amber for active session

        self.timer.start(1000) # Start the timer for display updates
        threading.Thread(target=self.run_focus_session, daemon=True).start()

    def run_focus_session(self):
        """
        Manages the focus session in a separate thread: opens apps,
        blocks shortcuts, and maintains focus on allowed windows.
        """
        self.block_shortcuts() # Call the instance method
        self._hide_taskbar() # Hide taskbar at session start

        # Launch SumatraPDF in fullscreen mode
        sumatra_path = self.get_sumatra_path()
        pdf_process = None
        if sumatra_path:
            try:
                pdf_process = subprocess.Popen([sumatra_path, '-fullscreen', self.pdf_path], shell=True if sys.platform.startswith('win') else False)
                print(f"Launched SumatraPDF: {self.pdf_path}")
            except Exception as e:
                print(f"Error launching SumatraPDF: {e}")
                self.status_message_label.setText(f"ERROR: Could not launch PDF viewer. {e}")
        else:
            print("SumatraPDF not found at expected paths.")
            self.status_message_label.setText("WARNING: SumatraPDF not found. PDF may not open.")


        # Launch Spotify
        spotify_process = None
        spotify_path = self.get_spotify_path()
        if spotify_path:
            try:
                spotify_process = subprocess.Popen([spotify_path], shell=True if sys.platform.startswith('win') else False)
                print("Launched Spotify.")
            except Exception as e:
                print(f"Error launching Spotify: {e}")
                self.status_message_label.setText(f"WARNING: Could not launch Spotify. {e}")
        else:
            print("Spotify not found at expected paths.")
            self.status_message_label.setText("WARNING: Spotify not found. Audio may not play.")

        # Give apps time to open and load
        time.sleep(6)

        pdf_window = None
        spotify_window = None
        # Max attempts to find windows
        for _ in range(15):
            all_windows = gw.getAllWindows()
            for w in all_windows:
                try:
                    title = w.title.lower()
                    if ".pdf" in title and pdf_window is None:
                        pdf_window = w
                    if "spotify" in title and spotify_window is None:
                        spotify_window = w
                except gw.PyGetWindowException:
                    pass
            if pdf_window and spotify_window:
                break
            time.sleep(1)
        
        # Store spotify_window_ref for the hotkey callback
        self.spotify_window_ref = spotify_window
        if self.spotify_window_ref:
            self.f6_hotkey_id = keyboard.add_hotkey('f6', self.activate_spotify_hotkey_callback)
            print("F6 hotkey registered for Spotify.")


        # Ensure PDF is maximized if found and not already
        if pdf_window and isinstance(pdf_window, gw.Win32Window):
            try:
                if not pdf_window.isMaximized:
                    pdf_window.maximize()
                pdf_window.activate()
                try:
                    pdf_window.alwaysOnTop(True)
                except Exception as e:
                    print(f"Could not set PDF window always on top: {e}")
            except gw.PyGetWindowException:
                print("PDF window became inaccessible during initial activation.")
                pdf_window = None


        # Store handles of allowed windows for focus enforcement
        allowed_handles = set()
        if pdf_window and isinstance(pdf_window, gw.Win32Window):
            allowed_handles.add(pdf_window._hWnd)
        if spotify_window and isinstance(spotify_window, gw.Win32Window):
            allowed_handles.add(spotify_window._hWnd)

        # Main focus loop
        while time.time() < self.end_time and self.session_active:
            current_active_window = gw.getActiveWindow()
            
            is_allowed = False
            if current_active_window is not None and isinstance(current_active_window, gw.Win32Window):
                try:
                    if current_active_window._hWnd in allowed_handles:
                        is_allowed = True
                except Exception:
                    pass
            
            if not is_allowed:
                # Prioritize activating PDF if it exists
                if pdf_window and isinstance(pdf_window, gw.Win32Window):
                    try:
                        if pdf_window.isMinimized:
                            pdf_window.restore()
                        pdf_window.activate()
                        pdf_window.raise_()
                    except gw.PyGetWindowException:
                        print("PDF window inaccessible during focus check, assuming closed.")
                        pdf_window = None
                # If PDF is gone or no longer active, try Spotify
                elif spotify_window and isinstance(spotify_window, gw.Win32Window):
                    try:
                        if spotify_window.isMinimized:
                            spotify_window.restore()
                        spotify_window.activate()
                        spotify_window.raise_()
                    except gw.PyGetWindowException:
                        print("Spotify window inaccessible during focus check, assuming closed.")
                        spotify_window = None
                # If neither allowed app is active, try to reactivate the PDF/Spotify process (more aggressive)
                else:
                    if pdf_process and pdf_process.poll() is None:
                        try:
                            subprocess.Popen([sumatra_path, '-fullscreen', self.pdf_path], shell=True if sys.platform.startswith('win') else False)
                            print("Re-launched SumatraPDF to regain focus.")
                        except Exception as e:
                            print(f"Error re-launching SumatraPDF: {e}")
                    elif spotify_process and spotify_process.poll() is None:
                        try:
                            subprocess.Popen([spotify_path], shell=True if sys.platform.startswith('win') else False)
                            print("Re-launched Spotify to regain focus.")
                        except Exception as e:
                            print(f"Error re-launching Spotify: {e}")

            time.sleep(0.5)

        self.unblock_shortcuts()
        self.end_session()

    def update_timer(self):
        """Updates the remaining time displayed on the UI."""
        remaining = max(0, int(self.end_time - time.time()))
        hrs, rem = divmod(remaining, 3600)
        mins, secs = divmod(rem, 60)
        self.timer_label.setText(f"Time Remaining: {hrs:02}:{mins:02}:{secs:02}")
        if remaining == 0:
            self.timer.stop()

    def end_session(self):
        """Resets the UI and unblocks shortcuts when the focus session ends."""
        if not self.session_active:
            return

        self.session_active = False
        self.unblock_shortcuts() # Ensure shortcuts are unblocked immediately
        self._show_taskbar()     # Show taskbar at session end

        # Unregister F6 hotkey if it was registered
        if self.f6_hotkey_id:
            try:
                keyboard.remove_hotkey(self.f6_hotkey_id)
                self.f6_hotkey_id = None
                print("F6 hotkey unregistered.")
            except Exception as e:
                print(f"Error unregistering F6 hotkey: {e}")
        self.spotify_window_ref = None # Clear reference to Spotify window

        # Restore window state and re-enable UI controls
        self.setVisible(True)
        self.setWindowFlags(Qt.Window) # Revert to a normal window type
        self.showNormal() # Restore to normal windowed mode
        self.activateWindow() # Bring app back to normal attention

        self.start_btn.setEnabled(True)
        self.select_btn.setEnabled(True)
        self.duration_combo.setEnabled(True)
        
        self.timer.stop()
        self.timer_label.setText("Time Remaining: 00:00:00")
        QMessageBox.information(self, "Focus Session Complete", "Your focus session has ended. Access restored.")
        self.status_message_label.setText("Session complete. Ready for next cycle.")
        self.status_message_label.setStyleSheet("color: #4CAF50;")


    def get_sumatra_path(self):
        """
        Returns the likely path to SumatraPDF executable on Windows.
        """
        if sys.platform.startswith('win'):
            paths = [
                os.path.expandvars(r"C:\Program Files\SumatraPDF\SumatraPDF.exe"),
                os.path.expandvars(r"C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe"),
                os.path.expandvars(r"%LOCALAPPDATA%\SumatraPDF\SumatraPDF.exe"),
            ]
            for path in paths:
                if os.path.exists(path):
                    return path
        return None

    def get_spotify_path(self):
        """
        Determines and returns the likely path to the Spotify executable based on the OS.
        Includes a direct check for the user-provided path from previous conversations.
        """
        if sys.platform.startswith('win'):
            # User-provided specific path from previous conversation
            user_spotify_path = r"Spotify\Spotify.exe"
            if os.path.exists(user_spotify_path):
                return user_spotify_path

            # Fallback to common install paths for Spotify
            appdata_path = os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe")
            localappdata_path = os.path.expandvars(r"%LOCALAPPDATA%\Spotify\Spotify.exe")
            programfiles_x86_path = os.path.expandvars(r"%ProgramFiles(x86)%\Spotify\Spotify.exe")

            if os.path.exists(appdata_path):
                return appdata_path
            elif os.path.exists(localappdata_path):
                return localappdata_path
            elif os.path.exists(programfiles_x86_path):
                return programfiles_x86_path
            else:
                return None
        elif sys.platform.startswith('darwin'):
            return "/Applications/Spotify.app/Contents/MacOS/Spotify"
        else: # Linux
            if os.path.exists("/usr/bin/spotify"):
                return "/usr/bin/spotify"
            return None

    def block_shortcuts(self):
        """Blocks common system shortcuts (Alt, Tab, Win, Esc, Ctrl, F11)."""
        for key in ['alt', 'tab', 'win', 'esc', 'ctrl', 'f11']:
            try:
                keyboard.block_key(key)
            except Exception:
                pass

    def unblock_shortcuts(self):
        """Unblocks previously blocked system shortcuts."""
        for key in ['alt', 'tab', 'win', 'esc', 'ctrl', 'f11']:
            try:
                keyboard.unblock_key(key)
            except Exception:
                pass

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        try:
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 6)
        except AttributeError:
            pass

    app = QApplication(sys.argv)
    window = ZenFocus()
    window.show()
    sys.exit(app.exec_())
