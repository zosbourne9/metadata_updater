import os
import shutil
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QPushButton, QComboBox, QFrame, QCheckBox,
    QMessageBox, QLineEdit, QDialog, QGridLayout, QScrollArea,
    QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QFont
from license_key import LicenseBanner, LicenseDialog

class DropOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create subtle glass morphism background frame
        self.frame = QFrame(self)
        self.frame.setStyleSheet("""
            QFrame {
                background-color: #374151
            }
        """)
        
        # Create subtle drop indicator label
        self.label = QLabel("🎵 Release to Drop Your Audio Files")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("""
            QLabel {
                color: #a0aec0;
                font-size: 18px;
                font-weight: 600;
                background-color: transparent;
                padding: 15px;
            }
        """)
        
        layout.addWidget(self.frame)
        self.label.setParent(self)
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Center the label
        self.label.setGeometry(0, 0, self.width(), self.height())

class UIElements(QWidget):
    def __init__(self, metadata_updater, version=None, license_manager=None):
        super().__init__()
        self.metadata_updater = metadata_updater
        self.version = version
        self.artist_warning_shown = False
        self.license_manager = license_manager
        self.setAcceptDrops(True)  # Enable drop for the entire window

        # Create overlay widget
        self.overlay = DropOverlay(self)
        self.overlay.hide()

        # Initialize checkbox variables
        self.select_all_var = QCheckBox("Select All")
        self.artist_var = QCheckBox("Artist")
        self.album_var = QCheckBox("Album")
        self.genre_var = QCheckBox("Genre")
        self.year_var = QCheckBox("Year")
        self.comments_var = QCheckBox("Subgenres")

        # Create status label
        self.status_label = QLabel("Ready To Process Files")
        
        self.setup_ui()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
            # Show overlay
            self.overlay.setGeometry(0, 0, self.width(), self.height())
            self.overlay.show()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        # Hide overlay
        self.overlay.hide()

    def dropEvent(self, event: QDropEvent):
        # Hide overlay
        self.overlay.hide()
        
        files = []
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith(('.mp3', '.m4a')):
                files.append(file_path)
        
        if files:
            self.on_drop(files)

    def setup_ui(self):
        # Set window properties
        self.setWindowTitle("Audio Metadata Manager")
        self.setMinimumSize(300, 525)
        self.setMaximumSize(450, 750)
        self.resize(360, 562)

        # UNIFIED BACKGROUND - Single color scheme throughout
        self.setStyleSheet("""
            QWidget {
                background-color: #374151;  /* Single unified background */
                color: #f3f4f6;
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
                font-size: 10px;
                font-weight: 400;
            }
            QLabel {
                font-size: 10px;
                color: #f3f4f6;
                background-color: transparent;
            }
            /* Remove all container backgrounds */
            QWidget#main_container {
                background-color: transparent;
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)

        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(9)
        main_layout.setContentsMargins(12, 12, 12, 12)
        
        # Create a main container
        main_container = QWidget()
        main_container.setObjectName("main_container")
        container_layout = QVBoxLayout(main_container)
        container_layout.setSpacing(12)
        container_layout.setContentsMargins(15, 15, 15, 15)
        main_container.setStyleSheet("""
                                     QWidget {
                                         background-color: #374151
                                     }
                                     """)

        # LICENSE BANNER - Minimal styling
        self.license_banner = LicenseBanner(self, self.license_manager)
        self.license_banner.setMaximumHeight(38)
        self.license_banner.setStyleSheet("""
            QWidget {
                background-color: #374151;
                border-radius: 6px;
                border: 1px solid rgba(255, 255, 255, 0.15);
            }
        """)
        container_layout.addWidget(self.license_banner)

        # HEADER - No background, just typography
        header_layout = QVBoxLayout()
        header_layout.setSpacing(3)
        
        title_label = QLabel("Audio Metadata Manager")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px; 
                font-weight: 600;
                color: #f9fafb;
                padding: 6px 0px;
                background-color: transparent;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        version_label = QLabel(f"v{self.version}")
        version_label.setStyleSheet("""
            QLabel {
                color: #9ca3af; 
                font-size: 9px;
                font-weight: 300;
                letter-spacing: 0.5px;
                background-color: transparent;
            }
        """)
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header_layout.addWidget(title_label)
        header_layout.addWidget(version_label)
        container_layout.addLayout(header_layout)

        # DROP ZONE - Minimal contrast
        drop_frame = QFrame()
        drop_frame.setFixedHeight(90)
        drop_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 0.15);
                border: 2px dashed rgba(156, 163, 175, 0.5);
                border-radius: 10px;
            }
            QFrame:hover {
                border: 2px dashed rgba(156, 163, 175, 0.8);
                background-color: rgba(0, 0, 0, 0.25);
            }
        """)
        drop_layout = QVBoxLayout(drop_frame)
        drop_layout.setContentsMargins(15, 15, 15, 15)
        
        self.drop_label = QLabel("🎵 Drop your audio files here\nor use the selection below")
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setStyleSheet("""
            QLabel {
                color: #d1d5db;
                font-size: 11px;
                font-weight: 400;
                line-height: 1.4;
                padding: 8px;
                background-color: transparent;
            }
        """)
        drop_layout.addWidget(self.drop_label)
        container_layout.addWidget(drop_frame)

        # FILE SELECTION - Cleaner buttons
        selection_frame = QFrame()
        selection_layout = QHBoxLayout(selection_frame)
        selection_layout.setContentsMargins(15, 0, 15, 0)
        selection_layout.setSpacing(9)
        
        self.combobox = QComboBox()
        self.combobox.addItems(['📁 File(s)', '📂 Folder'])
        self.combobox.setStyleSheet("""
            QComboBox {
                background-color: rgba(0, 0, 0, 0.3);
                color: #f3f4f6;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                padding: 6px 9px;
                min-width: 90px;
                font-size: 10px;
                font-weight: 500;
            }
            QComboBox:hover {
                background-color: rgba(0, 0, 0, 0.4);
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
            QComboBox::drop-down {
                border: none;
                width: 15px;
            }
            QComboBox::down-arrow {
                image: none;
                border-style: solid;
                border-width: 3px 3px 0px 3px;
                border-color: #d1d5db transparent transparent transparent;
            }
        """)

        self.select_files_btn = QPushButton("✨ Select Files")
        self.select_files_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 10px;
                font-weight: 600;
                min-height: 15px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
        """)

        selection_layout.addWidget(self.combobox, 1)
        selection_layout.addWidget(self.select_files_btn, 2)
        container_layout.addWidget(selection_frame)

        # METADATA FIELDS - Subtle section
        metadata_frame = QFrame()
        metadata_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 0.15);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 9px;
            }
        """)
        metadata_layout = QVBoxLayout(metadata_frame)
        metadata_layout.setContentsMargins(12, 9, 12, 12)
        metadata_layout.setSpacing(9)

        metadata_title = QLabel("🎛️ Select Metadata Fields")
        metadata_title.setStyleSheet("""
            QLabel {
                color: #f9fafb; 
                font-size: 12px; 
                font-weight: 600;
                padding: 3px 0px;
                background-color: transparent;
            }
        """)
        metadata_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        metadata_layout.addWidget(metadata_title)

        # TOGGLE BUTTONS - High contrast
        toggle_style = """
            QPushButton {
                color: #d1d5db;
                background-color: rgba(0, 0, 0, 0.25);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 6px 9px;
                font-size: 9px;
                font-weight: 500;
                text-align: center;
                min-height: 24px;
            }
            QPushButton:checked {
                background-color: #10b981;
                color: white;
                border: 1px solid rgba(16, 185, 129, 0.6);
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.35);
                border: 1px solid rgba(255, 255, 255, 0.25);
                color: #f9fafb;
            }
            QPushButton:checked:hover {
                background-color: #059669;
            }
        """

        # Create toggles grid
        toggles_grid = QGridLayout()
        toggles_grid.setSpacing(6)

        # Create buttons
        self.select_all_var = QPushButton("✅ All")
        self.artist_var = QPushButton("🎤 Artist")
        self.album_var = QPushButton("💿 Album")
        self.genre_var = QPushButton("🎵 Genre")
        self.year_var = QPushButton("📅 Year")
        self.comments_var = QPushButton("🏷️ Subgenres")

        button_pairs = [
            (self.select_all_var, "✅ All"),
            (self.artist_var, "🎤 Artist"),
            (self.album_var, "💿 Album"),
            (self.genre_var, "🎵 Genre"),
            (self.year_var, "📅 Year"),
            (self.comments_var, "🏷️ Subgenres")
        ]

        for i, (button, text) in enumerate(button_pairs):
            button.setCheckable(True)
            button.setText(text)
            button.setStyleSheet(toggle_style)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            row = i // 2
            col = i % 2
            toggles_grid.addWidget(button, row, col)

        metadata_layout.addLayout(toggles_grid)
        container_layout.addWidget(metadata_frame)

        # STATUS SECTION - Minimal styling
        status_frame = QFrame()
        status_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 9px;
            }
        """)
        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(12, 9, 12, 12)
        status_layout.setSpacing(6)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(15)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 8px;
                background-color: rgba(0, 0, 0, 0.3);
                text-align: center;
                color: white;
                font-size: 8px;
                font-weight: 600;
            }
            QProgressBar::chunk {
                background-color: #3b82f6;
                border-radius: 8px;
            }
        """)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        status_layout.addWidget(self.progress_bar)

        # Status labels
        self.current_file_label = QLabel("🎵 Ready To Process Files")
        self.current_file_label.setStyleSheet("""
            QLabel {
                font-size: 10px; 
                color: #d1d5db;
                font-weight: 600;
                padding: 4px;
                background-color: transparent;
            }
        """)
        self.current_file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_file_label.setWordWrap(True)
        status_layout.addWidget(self.current_file_label)

        self.status_label = QLabel("Select files to begin processing")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 9px; 
                color: #9ca3af;
                font-weight: 400;
                padding: 3px;
                background-color: transparent;
            }
        """)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)

        container_layout.addWidget(status_frame)

        # ACTION BUTTONS - High contrast
        buttons_frame = QFrame()
        buttons_layout = QVBoxLayout(buttons_frame)
        buttons_layout.setSpacing(9)

        # Primary buttons
        primary_buttons = QHBoxLayout()
        primary_buttons.setSpacing(9)

        primary_button_style = """
            QPushButton {
                background-color: #3b82f6;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 9px 15px;
                font-size: 10px;
                font-weight: 600;
                min-height: 27px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: rgba(0, 0, 0, 0.2);
                color: #6b7280;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        """

        self.update_tags_btn = QPushButton("✨ Update Tags")
        self.update_tags_btn.setStyleSheet(primary_button_style)
        self.update_tags_btn.setEnabled(False)
        primary_buttons.addWidget(self.update_tags_btn)

        self.update_filenames_btn = QPushButton("📝 Update Filenames")
        self.update_filenames_btn.setStyleSheet(primary_button_style)
        self.update_filenames_btn.setEnabled(False)
        primary_buttons.addWidget(self.update_filenames_btn)

        buttons_layout.addLayout(primary_buttons)

        # Secondary buttons
        secondary_buttons = QHBoxLayout()
        secondary_buttons.setSpacing(6)

        secondary_button_style = """
            QPushButton {
                background-color: rgba(0, 0, 0, 0.25);
                color: #ef4444;
                border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 6px;
                padding: 6px 9px;
                font-size: 8px;
                font-weight: 500;
                min-height: 21px;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.1);
                border: 1px solid rgba(239, 68, 68, 0.5);
                color: #f87171;
            }
        """

        warning_button_style = secondary_button_style.replace("#ef4444", "#f59e0b").replace("239, 68, 68", "245, 158, 11")

        self.clear_cache_btn = QPushButton("🗑️ Clear")
        self.clear_cache_btn.setStyleSheet(secondary_button_style)

        self.cancel_button = QPushButton("✋ Cancel")
        self.cancel_button.setStyleSheet(secondary_button_style)

        self.reset_app_btn = QPushButton("🔄 Reset")
        self.reset_app_btn.setStyleSheet(warning_button_style)

        secondary_buttons.addWidget(self.clear_cache_btn)
        secondary_buttons.addWidget(self.cancel_button)
        secondary_buttons.addWidget(self.reset_app_btn)

        buttons_layout.addLayout(secondary_buttons)
        container_layout.addWidget(buttons_frame)
        
        main_layout.addWidget(main_container)

        # Connect signals
        self.select_all_var.clicked.connect(self.toggle_select_all)
        self.artist_var.clicked.connect(self.on_artist_toggle)
        self.clear_cache_btn.clicked.connect(self.clear_all_caches)
        self.cancel_button.clicked.connect(self.metadata_updater.request_cancel)
        self.reset_app_btn.clicked.connect(self.metadata_updater.reset_application)
        self.select_files_btn.clicked.connect(self.metadata_updater.select_files_or_folder_threaded)
        self.update_tags_btn.clicked.connect(self.on_update_tags)
        self.update_filenames_btn.clicked.connect(self.metadata_updater.update_filenames)

        # Connect license banner change key button
        self.license_banner.license_btn.clicked.connect(self.show_license_dialog)

    def on_update_tags(self):
        """Handle update tags button click."""
        selected_fields = []
        if self.artist_var.isChecked():
            selected_fields.append('artist')
        if self.album_var.isChecked():
            selected_fields.append('album')
        if self.genre_var.isChecked():
            selected_fields.append('genre')
        if self.year_var.isChecked():
            selected_fields.append('year')
        if self.comments_var.isChecked():
            selected_fields.append('comments')

        if not selected_fields:
            QMessageBox.warning(
                self,
                "Warning",
                "Please select at least one metadata field to update.",
                QMessageBox.StandardButton.Ok
            )
            return

        self.metadata_updater.start_update_thread(selected_fields)

    def show_license_dialog(self):
        """Open the license dialog."""
        dialog = LicenseDialog(self, self.license_manager)
        dialog.exec()

    def toggle_select_all(self, checked):
        buttons = [self.album_var, self.genre_var, 
                self.year_var, self.comments_var]
        for button in buttons:
            button.setChecked(self.select_all_var.isChecked())

    def on_artist_toggle(self, checked):
        if self.artist_var.isChecked() and not self.artist_warning_shown:
            response = QMessageBox.warning(
                self,
                "Warning",
                "Modifying artist names may affect file organization and automation. Are you sure you want to proceed?",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel
            )
            if response == QMessageBox.StandardButton.Cancel:
                self.artist_var.setChecked(False)
                return
            self.artist_warning_shown = True

    def on_drop(self, files):
        """Handle dropped files with better feedback."""
        if files:
            # Validate files exist and are accessible
            valid_files = []
            for file_path in files:
                try:
                    if os.path.exists(file_path) and os.access(file_path, os.R_OK):
                        valid_files.append(file_path)
                    else:
                        print(f"File not accessible: {file_path}")
                except Exception as e:
                    print(f"Error validating file {file_path}: {e}")
            
            if valid_files:
                self.metadata_updater.selected_files = valid_files
                # Reset progress bar and update labels
                self.progress_bar.setValue(0)
                self.current_file_label.setText("Ready To Process Files")
                self.status_label.setText(f"Ready to process {len(valid_files)} file(s)")
                self.update_tags_btn.setEnabled(True)
                self.update_filenames_btn.setEnabled(True)
            else:
                self.status_label.setText("No valid/accessible audio files were found")
                self.progress_bar.setValue(0)
                self.update_tags_btn.setEnabled(False)
                self.update_filenames_btn.setEnabled(False)
        else:
            self.status_label.setText("No valid audio files were dropped")
            self.progress_bar.setValue(0)

    def clear_all_caches(self):
        """Clear all caches."""
        try:
            self.metadata_updater.cache_manager.clear()
            self.metadata_updater.spotify.clear_cache()
            self.metadata_updater.musicbrainz.clear_cache()

            cache_dir = os.environ.get(
                'CACHE_DIR', 
                os.path.expanduser('~/Library/Application Support/Metadata Updater')
            )
            if os.path.exists(cache_dir):
                try:
                    shutil.rmtree(cache_dir)
                    os.makedirs(cache_dir, exist_ok=True)
                except Exception as e:
                    print(f"Error removing cache directory: {e}")

            self.status_label.setText("All caches cleared successfully")
            print("All cache files cleared")

        except Exception as e:
            error_msg = f"Error clearing caches: {e}"
            self.status_label.setText(error_msg)
            print(error_msg)