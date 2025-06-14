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
from PyQt5.QtCore import QTimer, Qt, QSize, QPoint
from PyQt5.QtGui import QIcon, QPixmap, QColor, QPalette
import ctypes # Needed for taskbar and task manager hiding/showing

# Import winsound for playing system sounds on Windows
try:
    import winsound
except ImportError:
    winsound = None # winsound is Windows-specific, set to None if not available

# Constants for ShowWindow (Windows API)
SW_HIDE = 0
SW_SHOW = 5

class TimerOverlay(QWidget):
    """
    A small, frameless, always-on-top, and movable window
    to display the timer during a focus session.
    """
    def __init__(self):
        super().__init__()
        # Added Qt.WindowDoesNotAcceptFocus to prevent it from gaining keyboard focus
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.BypassWindowManagerHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground) # Make background truly transparent
        self.setFixedSize(200, 80) # Compact size for the timer

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(0)

        self.timer_display_label = QLabel("00:00:00")
        self.timer_display_label.setAlignment(Qt.AlignCenter)
        self.timer_display_label.setStyleSheet("""
            QLabel {
                color: #81C784; /* Green for focus */
                font-size: 26px;
                font-weight: bold;
                letter-spacing: 1px;
                /* text-shadow: 0 0 8px rgba(129, 199, 132, 0.7); /* Subtle glow */
                background-color: rgba(26, 46, 80, 0.8); /* Semi-transparent background */
                border-radius: 10px;
                padding: 5px;
            }
        """)
        self.layout.addWidget(self.timer_display_label)

        self.mode_label = QLabel("FOCUS")
        self.mode_label.setAlignment(Qt.AlignCenter)
        self.mode_label.setStyleSheet("""
            QLabel {
                color: #FFC107; /* Amber for active mode */
                font-size: 12px;
                font-weight: bold;
                letter-spacing: 0.5px;
                background-color: transparent;
            }
        """)
        self.layout.addWidget(self.mode_label)

        self.old_pos = None # For window dragging

    def update_timer_text(self, text, mode_text, mode_color):
        """Updates the timer and mode display."""
        self.timer_display_label.setText(text)
        self.timer_display_label.setStyleSheet(f"""
            QLabel {{
                color: {mode_color};
                font-size: 26px;
                font-weight: bold;
                letter-spacing: 1px;
                /* text-shadow: 0 0 8px {mode_color.replace('rgb', 'rgba').replace(')', ', 0.7)')}; */
                background-color: rgba(26, 46, 80, 0.8);
                border-radius: 10px;
                padding: 5px;
            }}
        """)
        self.mode_label.setText(mode_text)
        self.mode_label.setStyleSheet(f"""
            QLabel {{
                color: {mode_color};
                font-size: 12px;
                font-weight: bold;
                letter-spacing: 0.5px;
                background-color: transparent;
            }}
        """)

    def mousePressEvent(self, event):
        """Records the initial mouse position for dragging."""
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        """Moves the window based on mouse drag."""
        if event.buttons() == Qt.LeftButton and self.old_pos is not None:
            delta = QPoint(event.globalPos() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        """Resets the old mouse position after dragging."""
        if event.button() == Qt.LeftButton:
            self.old_pos = None

    def closeEvent(self, event):
        """Prevent closing the overlay directly during a session."""
        event.ignore() # Always ignore direct close attempts to keep it persistent

    def keyPressEvent(self, event):
        """Ignores key presses to prevent accidental interaction."""
        event.ignore()


class ZenFocus(QWidget):
    """
    A PyQt5 application designed to help users focus by locking them into
    a PDF viewer and Spotify, while blocking common system shortcuts.
    This version includes taskbar hiding, an F6 shortcut for Spotify,
    a Pomodoro-like break system with audible cues, and a separate timer overlay.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Silragon Focus Lock")
        self.setFixedSize(520, 420) # Main window size
        self.setWindowIcon(self.load_icon("dragon_icon.png"))

        self.pdf_path = None
        self.total_session_duration_minutes = 45
        self.focus_interval_minutes = 25
        self.break_interval_minutes = 5
        self.session_end_absolute_time = None

        self.session_active = False
        self.is_on_break = False
        self.current_segment_end_time = None

        self.spotify_window_ref = None
        self.f6_hotkey_id = None

        self.timer_overlay = None # Instance of the new TimerOverlay window

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

    def play_system_sound(self, frequency, duration_ms):
        """Plays a system sound using winsound on Windows, or prints a message otherwise."""
        if winsound:
            try:
                winsound.Beep(frequency, duration_ms)
            except Exception as e:
                print(f"Error playing sound: {e}")
        else:
            print(f"Playing sound (freq: {frequency}Hz, dur: {duration_ms}ms) - (winsound not available on this OS)")

    def get_stylesheet(self):
        """
        Returns the stylesheet with the modified navy color scheme
        and subtle accents, adapted for new buttons and layout.
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
        QLabel#timerLabel { /* This will now be primarily for initial state/reset */
            font-size: 28px;
            font-weight: bold;
            color: #81C784;
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
            border-radius: 15px; /* Smoother, more rounded corners */
            font-size: 16px;
            font-weight: bold;
            padding: 12px 25px; /* Increased padding for smoother feel */
            border: 2px solid #3F51B5; /* Distinct border for samurai-like edge */
            min-width: 120px;
            letter-spacing: 0.5px; /* Subtle letter spacing */
        }
        QPushButton:hover {
            background-color: #1976D2; /* Darker Blue on hover */
            border-color: #90CAF9; /* Lighter border on hover */
            color: #E0EBF5; /* Slight color change on hover */
        }
        QPushButton:pressed {
            background-color: #1565C0; /* Even darker on press */
            border-color: #2196F3; /* Revert border to primary on press */
        }
        QPushButton#selectPdfButton { /* Separate style for Select PDF button */
            background-color: #64B5F6; /* Lighter Blue */
            color: white;
            padding: 10px 18px; /* Adjusted padding */
            font-size: 14px;
            border-radius: 12px; /* Smoother */
            border: 1px solid #3F51B5; /* Consistent border style */
        }
        QPushButton#selectPdfButton:hover {
            background-color: #42A5F5;
            border-color: #90CAF9;
        }
        QPushButton#resetButton { /* Style for the new Reset button */
            background-color: #FF5252; /* Red for reset */
            border-color: #FF1744;
            color: white;
            font-size: 15px;
            font-weight: bold;
            padding: 10px 20px;
            border-radius: 12px;
        }
        QPushButton#resetButton:hover {
            background-color: #D32F2F;
            border-color: #FF5252;
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
            pixmap = pixmap.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation) # Scale for header
            dragon_icon_label.setPixmap(pixmap)
        dragon_icon_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        dragon_icon_label.setFixedSize(QSize(48, 48))

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
        duration_label = QLabel("Total Duration (minutes):") # Label changed for clarity
        duration_layout.addWidget(duration_label)

        self.duration_combo = QComboBox()
        self.duration_combo.addItems(["45", "60", "90", "120", "150", "180"]) # Adjusted for Pomodoro multiples
        self.duration_combo.setCurrentText("90") # Default to 90 min (2 focus, 1 break)
        duration_layout.addWidget(self.duration_combo)
        duration_layout.addStretch()
        frame_layout.addLayout(duration_layout)

        # Buttons layout for Start and Reset
        button_row_layout = QHBoxLayout()
        self.start_btn = QPushButton("Initiate Focus Lock ?")
        self.start_btn.clicked.connect(self.start_focus)
        self.start_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button_row_layout.addWidget(self.start_btn)

        self.reset_btn = QPushButton("Reset Session") # New Reset Button
        self.reset_btn.setObjectName("resetButton")
        self.reset_btn.clicked.connect(self.reset_session)
        self.reset_btn.setEnabled(False) # Disabled initially
        button_row_layout.addWidget(self.reset_btn)
        frame_layout.addLayout(button_row_layout)


        # Timer display - This will now only show initial state or reset
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
        """Hides the Windows taskbar and Start button, and Task Manager."""
        if sys.platform.startswith('win'):
            try:
                # Hide Taskbar
                taskbar_hwnd = ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None)
                if taskbar_hwnd:
                    ctypes.windll.user32.ShowWindow(taskbar_hwnd, SW_HIDE)
                    print("Taskbar hidden successfully.")
                else:
                    print("Taskbar window not found.")

                # Hide Start button
                start_button_hwnd = ctypes.windll.user32.FindWindowW("Button", "Start")
                if start_button_hwnd:
                    ctypes.windll.user32.ShowWindow(start_button_hwnd, SW_HIDE)
                    print("Start button hidden successfully.")
                else:
                    print("Start button window not found.")
                
                # Hide Task Manager
                # FindWindowW can take class name or window title.
                # Common Task Manager class names: "TaskManagerWindow", "Task Manager" (title)
                task_manager_hwnd = ctypes.windll.user32.FindWindowW("TaskManagerWindow", None) 
                if not task_manager_hwnd:
                    task_manager_hwnd = ctypes.windll.user32.FindWindowW(None, "Task Manager") # Fallback by title
                
                if task_manager_hwnd:
                    ctypes.windll.user32.ShowWindow(task_manager_hwnd, SW_HIDE)
                    print("Task Manager hidden successfully.")
                else:
                    print("Task Manager window not found.")

            except Exception as e:
                print(f"Error hiding system UI elements: {e}")

    def _show_taskbar(self):
        """Shows the Windows taskbar and Start button, and Task Manager."""
        if sys.platform.startswith('win'):
            try:
                # Show Taskbar
                taskbar_hwnd = ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None)
                if taskbar_hwnd:
                    ctypes.windll.user32.ShowWindow(taskbar_hwnd, SW_SHOW)
                    print("Taskbar shown successfully.")
                else:
                    print("Taskbar window not found for showing.")

                # Show Start button
                start_button_hwnd = ctypes.windll.user32.FindWindowW("Button", "Start")
                if start_button_hwnd:
                    ctypes.windll.user32.ShowWindow(start_button_hwnd, SW_SHOW)
                    print("Start button shown successfully.")
                else:
                    print("Start button window not found for showing.")

                # Show Task Manager
                task_manager_hwnd = ctypes.windll.user32.FindWindowW("TaskManagerWindow", None)
                if not task_manager_hwnd:
                    task_manager_hwnd = ctypes.windll.user32.FindWindowW(None, "Task Manager")
                
                if task_manager_hwnd:
                    ctypes.windll.user32.ShowWindow(task_manager_hwnd, SW_SHOW)
                    print("Task Manager shown successfully.")
                else:
                    print("Task Manager window not found for showing.")

            except Exception as e:
                print(f"Error showing system UI elements: {e}")

    def activate_spotify_hotkey_callback(self):
        """
        Callback function for the F6 hotkey to toggle Spotify's minimized/restored state.
        """
        if self.session_active and self.spotify_window_ref and isinstance(self.spotify_window_ref, gw.Win32Window):
            try:
                if self.spotify_window_ref.isMinimized:
                    self.spotify_window_ref.restore()
                    self.spotify_window_ref.activate()
                    self.spotify_window_ref.raise_()
                    print("F6 pressed: Restored and activated Spotify.")
                else:
                    # If it's not minimized, minimize it
                    self.spotify_window_ref.minimize()
                    print("F6 pressed: Minimized Spotify.")
            except Exception as e:
                print(f"Error toggling Spotify via F6: {e}")
        else:
            print("F6 pressed, but Spotify window not found or session not active.")

    def start_focus(self):
        """Initiates the focus lock session."""
        if not self.pdf_path:
            QMessageBox.warning(self, "Error", "Please select a PDF file first.")
            return

        self.total_session_duration_minutes = int(self.duration_combo.currentText())
        self.session_end_absolute_time = time.time() + self.total_session_duration_minutes * 60
        self.session_active = True
        self.is_on_break = False # Start in focus mode
        self.current_segment_end_time = time.time() + (self.focus_interval_minutes * 60) # Initial focus segment end

        # Create and show the Timer Overlay window
        self.timer_overlay = TimerOverlay()
        # Position it in the top-right corner, adjusted slightly
        screen_geometry = QApplication.desktop().screenGeometry()
        self.timer_overlay.move(screen_geometry.width() - self.timer_overlay.width() - 20, 20)
        self.timer_overlay.show()
        
        # Main UI window hides during session
        self.showMinimized()
        self.setVisible(False)

        # Disable input controls and enable reset button
        self.start_btn.setEnabled(False)
        self.select_btn.setEnabled(False)
        self.duration_combo.setEnabled(False)
        self.reset_btn.setEnabled(True)
        
        self.status_message_label.setText("FOCUS MODE ACTIVE. Stay strong!")
        self.status_message_label.setStyleSheet("color: #FFC107;") # Amber for active session

        self.timer.start(1000) # Start the timer for display updates
        threading.Thread(target=self.run_focus_session, daemon=True).start()

    def run_focus_session(self):
        """
        Manages the focus session in a separate thread, alternating between focus and break.
        """
        self.block_shortcuts() # Block general shortcuts at session start
        self._hide_taskbar() # Hide taskbar at session start

        # Launch SumatraPDF
        sumatra_path = self.get_sumatra_path()
        pdf_process = None
        if sumatra_path:
            try:
                # Launch without -fullscreen initially, as we'll send F5 later
                pdf_process = subprocess.Popen([sumatra_path, self.pdf_path], shell=True if sys.platform.startswith('win') else False)
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


        # Ensure PDF is maximized and activated, then send F5 for full-screen and block F5
        if pdf_window and isinstance(pdf_window, gw.Win32Window):
            try:
                if not pdf_window.isMaximized:
                    pdf_window.maximize()
                pdf_window.activate()
                try:
                    pdf_window.alwaysOnTop(True)
                except Exception as e:
                    print(f"Could not set PDF window always on top: {e}")
                
                time.sleep(1) # Give it a moment to fully activate
                
                # Activate again right before sending key to ensure focus
                pdf_window.activate()
                pdf_window.raise_()
                time.sleep(0.1) # Small delay for focus change

                # Send F5 ONCE and then immediately block it for the rest of the session
                try:
                    keyboard.send('f5') # Send F5 to SumatraPDF
                    print("Sent F5 to SumatraPDF for full-screen activation.")
                    time.sleep(0.1) # Short delay to allow keypress to register
                    keyboard.block_key('f5') # Block F5 immediately after sending it
                    print("F5 key blocked for user input for the session duration.")
                except Exception as e:
                    print(f"Error sending F5 to SumatraPDF or blocking F5: {e}")

            except gw.PyGetWindowException:
                print("PDF window became inaccessible during initial activation.")
                pdf_window = None


        # Store handles of allowed windows for focus enforcement
        allowed_handles = set()
        if pdf_window and isinstance(pdf_window, gw.Win32Window):
            allowed_handles.add(pdf_window._hWnd)
        if spotify_window and isinstance(spotify_window, gw.Win32Window):
            allowed_handles.add(spotify_window._hWnd)

        # Main session loop (alternating focus and break)
        while time.time() < self.session_end_absolute_time and self.session_active:
            current_time = time.time()

            # Check for segment transition
            if current_time >= self.current_segment_end_time:
                if not self.is_on_break: # End of focus segment, start break
                    self.is_on_break = True
                    self.play_system_sound(880, 500) # Higher pitch for break start
                    # Updated: Status message for main window in red for break
                    self.status_message_label.setText("BREAK TIME! 5 minutes. Relax.")
                    self.status_message_label.setStyleSheet("color: #F44336;") # Red for break
                    self.unblock_shortcuts() # Unblock general shortcuts for break
                    self._show_taskbar() # Show taskbar for break
                    
                    # F5 is *not* in the general unblock_shortcuts list, so it remains blocked.
                    # This is correct if it should be blocked during breaks too.

                    # Optionally minimize/deactivate focus apps during break
                    if pdf_window and isinstance(pdf_window, gw.Win32Window):
                        try:
                            pdf_window.minimize()
                        except gw.PyGetWindowException:
                            pass
                    if spotify_window and isinstance(spotify_window, gw.Win32Window):
                        try:
                            spotify_window.minimize()
                        except gw.PyGetWindowException:
                            pass
                    self.current_segment_end_time = current_time + (self.break_interval_minutes * 60)
                    print("Transitioned to break mode.")
                else: # End of break segment, resume focus
                    self.is_on_break = False
                    self.play_system_sound(660, 500) # Lower pitch for break end
                    self.status_message_label.setText("BACK TO FOCUS! Resume work.")
                    self.status_message_label.setStyleSheet("color: #4CAF50;") # Green for focus
                    self.block_shortcuts() # Re-block general shortcuts for focus
                    self._hide_taskbar() # Hide taskbar for focus

                    # F5 remains blocked from its initial block_key call throughout.
                    # We do NOT send F5 again here, as per "only once".

                    # Aggressively re-activate PDF (without sending F5 again)
                    if pdf_window and isinstance(pdf_window, gw.Win32Window):
                        for _ in range(3): # Try a few times to re-assert focus
                            try:
                                if pdf_window.isMinimized:
                                    pdf_window.restore()
                                pdf_window.activate()
                                pdf_window.raise_()
                                time.sleep(0.5) # Give some time for window to react
                                print("Re-activated SumatraPDF after break (F5 not re-sent).")
                                break # Break from retry loop if successful
                            except gw.PyGetWindowException:
                                print("PDF window inaccessible during post-break activation attempt.")
                                pdf_window = None # Mark as inaccessible if consistent failure
                                break # Exit retry loop
                            except Exception as e:
                                print(f"Error during post-break PDF re-activation: {e}")
                                time.sleep(0.5) # Wait before next retry

                    if spotify_window and isinstance(spotify_window, gw.Win32Window):
                        try:
                            spotify_window.restore()
                            spotify_window.activate()
                            spotify_window.raise_()
                        except gw.PyGetWindowException:
                            pass
                    
                    # Ensure the timer overlay is still on top
                    if self.timer_overlay and self.timer_overlay.isVisible():
                        self.timer_overlay.activateWindow()
                        self.timer_overlay.raise_()
                        time.sleep(0.1) # Brief pause after main app activation


                    # Calculate next focus segment end, respecting total session duration
                    remaining_total = self.session_end_absolute_time - current_time
                    next_focus_duration = min(self.focus_interval_minutes * 60, remaining_total)
                    if next_focus_duration > 0:
                        self.current_segment_end_time = current_time + next_focus_duration
                    else:
                        break # End session if no more focus time left
                    print("Transitioned to focus mode.")

            # Focus enforcement only during focus mode
            if not self.is_on_break:
                current_active_window = gw.getActiveWindow()
                is_allowed = False
                if current_active_window is not None and isinstance(current_active_window, gw.Win32Window):
                    try:
                        # Check if the active window is one of our allowed focus apps OR the timer overlay itself
                        if current_active_window._hWnd in allowed_handles or \
                           (self.timer_overlay and self.timer_overlay.isVisible() and current_active_window._hWnd == self.timer_overlay.winId()):
                            is_allowed = True
                    except Exception:
                        pass
                
                if not is_allowed:
                    # Prioritize activating PDF
                    if pdf_window and isinstance(pdf_window, gw.Win32Window):
                        try:
                            if pdf_window.isMinimized: pdf_window.restore()
                            pdf_window.activate()
                            pdf_window.raise_()
                        except gw.PyGetWindowException:
                            print("PDF window inaccessible, assuming closed during focus.")
                            pdf_window = None
                    # Fallback to Spotify if PDF fails
                    elif spotify_window and isinstance(spotify_window, gw.Win32Window):
                        try:
                            if spotify_window.isMinimized: spotify_window.restore()
                            spotify_window.activate()
                            spotify_window.raise_()
                        except gw.PyGetWindowException:
                            print("Spotify window inaccessible, assuming closed during focus.")
                            spotify_window = None
                    # If all specific apps are gone, try to relaunch or just let the main app serve as a blocker
                    else:
                        if pdf_process and pdf_process.poll() is None: # If PDF process is still running
                            try: subprocess.Popen([sumatra_path, self.pdf_path], shell=True if sys.platform.startswith('win') else False)
                            except Exception as e: print(f"Error re-launching SumatraPDF: {e}")
                        elif spotify_process and spotify_process.poll() is None:
                            try: subprocess.Popen([spotify_path], shell=True if sys.platform.startswith('win') else False)
                            except Exception as e: print(f"Error re-launching Spotify: {e}")
                        
                        # Ensure the timer overlay is still on top if other apps fail
                        if self.timer_overlay and self.timer_overlay.isVisible():
                            self.timer_overlay.activateWindow()
                            self.timer_overlay.raise_()
                        time.sleep(0.1) # Brief pause

            time.sleep(0.5) # Check every half second

        # Session ended naturally or forced out of loop
        self.unblock_shortcuts() # This unblocks all general shortcuts
        # Explicitly unblock F5 one last time
        try:
            keyboard.unblock_key('f5')
            print("F5 unblocked at session end.")
        except Exception:
            pass
        self.end_session() # This will run cleanup

    def update_timer(self):
        """Updates the remaining time displayed on the UI based on current segment."""
        # Remaining time for the current segment
        remaining_segment = max(0, int(self.current_segment_end_time - time.time()))
        
        # Total remaining time for the entire session (for information, not controlling loop)
        total_remaining = max(0, int(self.session_end_absolute_time - time.time()))

        if self.session_active:
            mode_text = "FOCUS MODE" if not self.is_on_break else "BREAK TIME"
            
            hrs_seg, rem_seg = divmod(remaining_segment, 3600)
            mins_seg, secs_seg = divmod(rem_seg, 60)
            segment_time_str = f"{hrs_seg:02}:{mins_seg:02}:{secs_seg:02}"

            # Only update the TimerOverlay if it exists
            if self.timer_overlay:
                # Updated: Use red for break time in the overlay
                mode_color = "#F44336" if self.is_on_break else "#81C784" # Red for break, Green for focus
                self.timer_overlay.update_timer_text(segment_time_str, mode_text, mode_color)

            # Update the main window's timer label as well (optional, since it's hidden)
            # This is more for consistency in data, if the main window were to be unhidden during session
            hrs_total, rem_total = divmod(total_remaining, 3600)
            mins_total, secs_total = divmod(rem_total, 60)
            self.timer_label.setText(
                f"{mode_text}: {hrs_seg:02}:{mins_seg:02}:{secs_seg:02}\n"
                f"(Total Left: {hrs_total:02}:{mins_total:02}:{secs_total:02})"
            )
            # The main window's timer label styling is largely irrelevant if it's hidden.

        if total_remaining == 0 and self.session_active: # Ensure it only triggers once at the very end
            self.timer.stop() # Stop timer when entire session runs out
            # Call end_session immediately here to ensure prompt cleanup
            self.end_session()


    def reset_session(self):
        """Removes the reset_session functionality entirely."""
        # The user's original code had this:
        # raise NotImplementedError("Resetting the session manually is not allowed to maintain strict focus. Please wait for the timer to complete.")
        # Reverting to enable reset functionality for debugging/user control, but can be re-disabled if strictness is paramount.
        # This function should terminate the running session and revert the UI.
        
        # Ensure session_active is set to False to stop the threading.Thread loop
        self.session_active = False 
        self.unblock_shortcuts()
        self._show_taskbar()
        if self.f6_hotkey_id:
            try:
                keyboard.remove_hotkey(self.f6_hotkey_id)
                self.f6_hotkey_id = None
            except Exception as e:
                print(f"Error unregistering F6 hotkey during reset: {e}")
        self.spotify_window_ref = None

        if self.timer_overlay:
            self.timer_overlay.close()
            self.timer_overlay = None

        self.setVisible(True)
        self.setWindowFlags(Qt.Window)
        self.showNormal()
        self.activateWindow()

        self.start_btn.setEnabled(True)
        self.select_btn.setEnabled(True)
        self.duration_combo.setEnabled(True)
        self.reset_btn.setEnabled(False)
        
        self.timer.stop()
        self.timer_label.setText("Time Remaining: --:--:--")
        self.status_message_label.setText("Session reset. Ready for new focus.")
        self.status_message_label.setStyleSheet("color: #E0EBF5;") # Default color for reset
        
        QMessageBox.information(self, "Session Reset", "The focus session has been reset.")


    def end_session(self):
        """Resets the UI and unblocks shortcuts when the focus session ends."""
        # This function is primarily called when the timer runs out naturally
        # or if an unrecoverable error occurs in run_focus_session.
        # If reset_session is called, it will handle most of this.

        if not self.session_active: # Only proceed if session was marked active (and not already ended by reset_session)
            return

        self.session_active = False # Mark as inactive (important for loop termination)
        self.unblock_shortcuts() # Ensure shortcuts are unblocked immediately
        self._show_taskbar()     # Show taskbar at session end

        # Unregister F6 hotkey
        if self.f6_hotkey_id:
            try:
                keyboard.remove_hotkey(self.f6_hotkey_id)
                self.f6_hotkey_id = None
                print("F6 hotkey unregistered.")
            except Exception as e:
                print(f"Error unregistering F6 hotkey: {e}")
        self.spotify_window_ref = None # Clear reference to Spotify window

        # Close the timer overlay if it exists
        if self.timer_overlay:
            self.timer_overlay.close()
            self.timer_overlay = None

        # Restore main window to normal state
        self.setVisible(True)
        self.setWindowFlags(Qt.Window) # Revert to a normal window type
        self.showNormal() # Restore to normal windowed mode
        self.activateWindow() # Bring app back to normal attention

        self.start_btn.setEnabled(True)
        self.select_btn.setEnabled(True)
        self.duration_combo.setEnabled(True)
        self.reset_btn.setEnabled(False) # Disable reset button until session starts again
        
        self.timer.stop()
        self.timer_label.setText("Time Remaining: 00:00:00")
        
        # Updated: Personalized congratulatory message
        QMessageBox.information(self, "Focus Session Complete", "Congrats Master Ryu for finishing your study session!")
        self.status_message_label.setText("Congrats Master Ryu for finishing your study session!")
        self.status_message_label.setStyleSheet("color: #81C784;") # Green for success/completion


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
            user_spotify_path = r"C:\Users\ahmed\AppData\Roaming\Spotify\Spotify.exe"
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
                return "/usr/bin/spotify" # Corrected path
            return None

    def block_shortcuts(self):
        """Blocks common system shortcuts (Alt, Tab, Win, Esc, Ctrl, F11).
        F5 is handled separately for specific blocking logic."""
        for key in ['alt', 'tab', 'win', 'esc', 'ctrl', 'f11']: # F5 removed from this list
            try:
                keyboard.block_key(key)
            except Exception:
                pass

    def unblock_shortcuts(self):
        """Unblocks previously blocked system shortcuts (excluding F5, which is separate)."""
        for key in ['alt', 'tab', 'win', 'esc', 'ctrl', 'f11']: # F5 removed from this list
            try:
                keyboard.unblock_key(key)
            except Exception:
                pass

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        try:
            # This line had a typo: `type.windll` should be `ctypes.windll`
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 6)
        except AttributeError:
            pass

    app = QApplication(sys.argv)
    window = ZenFocus()
    window.show()
    sys.exit(app.exec_())
