import sys
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog, QTabWidget, QHBoxLayout, QTextEdit, QSizePolicy, QSpacerItem, QListWidget, QMessageBox
)
from PyQt5.QtGui import QPixmap, QImage, QIcon, QClipboard
from PyQt5.QtCore import Qt, QTimer, QEvent
from PIL import Image
from pyzbar.pyzbar import decode
import qrcode
import cv2
import os
import tempfile

# code for pyinstaller paths
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS2
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class QRCodeGeneratorDecoder(QWidget):
    def __init__(self):
        super().__init__()

        self.initUI()
        self.cap = None
        self.pause_video = False
        self.setStyleSheet("""
        background-color: #282828;
        border-top: 2px solid #303030;  /* Adjust #303030 for border shade */
        color: white;  /* Applies to all text within the app */
        """)
        # Counter for generated QR codes
        self.qr_code_counter = 1


    def initUI(self):
        self.setWindowTitle('QR Code Generator and Decoder')
        self.setGeometry(100, 100, 600, 400)  # Increase window size

        # Create tabs
        self.tab_widget = QTabWidget(self)

        self.encode_tab = QWidget()
        self.decode_tab = QWidget()

        self.tab_widget.addTab(self.encode_tab, "Encode")
        self.tab_widget.addTab(self.decode_tab, "Decode")

        # Set up layouts for each tab
        self.initEncodeTabLayout()
        self.initDecodeTabLayout()

        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self.tab_widget)

        self.setLayout(main_layout)

        # Create the Wi-Fi sharing tab
        self.wifi_tab = QWidget()
        self.tab_widget.addTab(self.wifi_tab, "Wi-Fi Sharing")

        # Set up layout for Wi-Fi sharing tab
        self.initWifiTabLayout()
        #setup bar width
        self.tab_widget.tabBar().setMinimumWidth(250)
        # set barStyleSheet
        self.tab_widget.setStyleSheet("""
        QTabBar::tab { background-color: #303030; color: white; }  /* Adjust #303030 for desired shade */
        QTabBar::tab:selected { border-bottom: 2px solid white; }  /* Add a white bottom border for selected tab */
        """)

    def initEncodeTabLayout(self):
        encode_layout = QVBoxLayout()

        # Text input area for encoding
        self.encode_input = QTextEdit(self)
        self.encode_input.setPlaceholderText("Enter text here...")
        self.encode_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        encode_layout.addWidget(self.encode_input)

        self.generate_button = QPushButton('Generate QR Code', self)
        self.generate_button.clicked.connect(self.generateQRCode)
        encode_layout.addWidget(self.generate_button, 0)  # Set stretch factor to 0

        # Display generated picture
        self.generated_picture_label = QLabel(self)
        encode_layout.addWidget(self.generated_picture_label)

        self.copy_button = QPushButton('Copy Image', self)
        self.copy_button.clicked.connect(self.copyImage)
        self.copy_button.hide()  # Initially hide the copy button
        encode_layout.addWidget(self.copy_button, 0)  # Set stretch factor to 0

        self.encode_tab.setLayout(encode_layout)

    def initDecodeTabLayout(self):
        decode_layout = QVBoxLayout()
        # Create and set up the drop_area widget
        self.drop_area = QLabel("Drag an image here or double-click to upload a file", self)
        self.drop_area.setAlignment(Qt.AlignCenter)
        self.drop_area.setStyleSheet("QLabel { border: 2px dashed #aaaaaa; padding: 120px; }")
        self.drop_area.setAcceptDrops(True)
        self.drop_area.mouseDoubleClickEvent = self.doubleClickEvent
        self.drop_area.installEventFilter(self)
        decode_layout.addWidget(self.drop_area)

        # Result label
        self.result_label = QLabel(self)
        decode_layout.addWidget(self.result_label)

        # Pause and Resume buttons (initially hidden)
        self.pause_button = QPushButton('Pause', self)
        self.pause_button.clicked.connect(self.pauseVideo)
        self.pause_button.setEnabled(False)
        decode_layout.addWidget(self.pause_button)

        self.resume_button = QPushButton('Resume', self)
        self.resume_button.clicked.connect(self.resumeVideo)
        self.resume_button.setEnabled(False)
        decode_layout.addWidget(self.resume_button)

        # Options for using the camera
        camera_layout = QHBoxLayout()

        # Add a spacer to push the "Use Camera" button to the right
        spacer_item = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        camera_layout.addItem(spacer_item)

        # Choose option button moved to the bottom line
        self.choose_option_button = QPushButton('Use Camera', self)
        self.choose_option_button.clicked.connect(self.startCamera)
        camera_layout.addWidget(self.choose_option_button)

        decode_layout.addLayout(camera_layout)

        # Video label
        self.video_label = QLabel(self)
        self.video_label.setAlignment(Qt.AlignCenter)
        decode_layout.addWidget(self.video_label)

        # Hide the camera-related widgets initially
        self.hideCameraWidgets()

        self.decode_tab.setLayout(decode_layout)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)

    def initWifiTabLayout(self):  # New function for Wi-Fi Sharing tab
        wifi_layout = QVBoxLayout()

        # Fetch Wi-Fi networks button
        self.fetch_wifi_button = QPushButton('Fetch Wi-Fi Networks', self)
        self.fetch_wifi_button.clicked.connect(self.fetchWifiNetworks)
        wifi_layout.addWidget(self.fetch_wifi_button)

        # List to display Wi-Fi networks
        self.wifi_list = QListWidget(self)
        wifi_layout.addWidget(self.wifi_list)

        # Share Wi-Fi password as QR Code button
        self.share_wifi_button = QPushButton('Share Wi-Fi Password as QR Code', self)
        self.share_wifi_button.clicked.connect(self.shareWifiPassword)
        wifi_layout.addWidget(self.share_wifi_button)

        self.wifi_tab.setLayout(wifi_layout)

    def fetchWifiNetworks(self):
        try:
            result = subprocess.run(['netsh', 'wlan', 'show', 'profiles'], capture_output=True, text=True)
            result.check_returncode()  # Raise an error if the subprocess call was not successful

            profiles = [line.split(":")[1].strip() for line in result.stdout.splitlines() if "All User Profile" in line]
            self.wifi_list.clear()
            self.wifi_list.addItems(profiles)
        except subprocess.CalledProcessError as e:
            self.showErrorMessage(f"Error fetching Wi-Fi networks: {e}")
        except Exception as e:
            self.showErrorMessage(f"An unexpected error occurred: {e}")

    def fetchWifiPassword(self, wifi_name):
        try:
            result = subprocess.run(['netsh', 'wlan', 'show', 'profile', wifi_name, 'key=clear'], capture_output=True, text=True)
            password_line = [line for line in result.stdout.splitlines() if "Key Content" in line]
            if password_line:
                password = password_line[0].split(":")[1].strip()
                return password
        except Exception as e:
            print(f"Error fetching Wi-Fi password: {e}")
        return None

    def shareWifiPassword(self):
        selected_item = self.wifi_list.currentItem()
        if selected_item:
            wifi_name = selected_item.text()
            password = self.fetchWifiPassword(wifi_name)
            if password:
                data_to_share = f"WIFI:S:{wifi_name};T:WPA;P:{password};;"
                # Display generated Wi-Fi QR code directly in the Wi-Fi tab
                self.generateAndDisplayQRCode(data_to_share, f"{wifi_name}_qrcode.png", layout=self.wifi_tab.layout())
                
    def generateAndDisplayQRCode(self, data, file_name, display_result=True, layout=None):
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()

        # Generate the full path to the temporary file
        temp_file_path = os.path.join(temp_dir, file_name)

        # Generate the QR code using the temporary file path
        generate_qrcode(data, file_name=temp_file_path)

        # Load the QR code from the temporary file
        pixmap = QPixmap(temp_file_path)

        if display_result:
            # Display generated picture
            self.generated_picture_label.setPixmap(pixmap)
            self.copy_button.show()

        if data.startswith("WIFI:S:"):
            # Display generated Wi-Fi password as QR code
            wifi_password_label = QLabel(self)
            wifi_password_label.setPixmap(pixmap)
            wifi_password_label.setAlignment(Qt.AlignCenter)

            # Add a spacer to push the QLabel to the top
            spacer_item = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
            layout.addItem(spacer_item)  # Use the provided layout parameter

            layout.addWidget(wifi_password_label)
            layout.setAlignment(wifi_password_label, Qt.AlignCenter)

        # Save the temporary directory and file path to the class attribute
        self.temp_dir = temp_dir
        self.temp_file_path = temp_file_path


    def doubleClickEvent(self, event):
        # Handle double-click event on the drop_area
        if event.button() == Qt.LeftButton:
            self.openFileExplorer()

    def openFileExplorer(self):
        # Open file explorer to select an image file
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        file_dialog.setNameFilter("Image files (*.png *.jpg *.bmp *.jpeg)")
        if file_dialog.exec_():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                image_path = selected_files[0]
                self.decodeQRCodeFromImage(image_path)

    def hideCameraWidgets(self):
        # Helper method to hide camera-related widgets
        self.choose_option_button.setEnabled(True)
        self.pause_button.hide()
        self.resume_button.hide()
        self.video_label.clear()

    def startCamera(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            self.showErrorMessage("Error: Unable to open camera.")
            return

        self.timer.start(100)  # Update every 100 milliseconds
        self.hideCameraWidgets()
        self.pause_button.setEnabled(True)
        self.resume_button.setEnabled(False)
        self.pause_button.show()
        self.resume_button.show()


    def dropEvent(self, event):
        #Handle drop event for files dropped onto the drop area.
        mime_data = event.mimeData()
        if mime_data.hasUrls() and len(mime_data.urls()) == 1 and mime_data.urls()[0].isLocalFile():
            image_path = mime_data.urls()[0].toLocalFile()
            self.decodeQRCodeFromImage(image_path)
            event.acceptProposedAction()

    def eventFilter(self, obj, event):
        #Override event filter for drag enter and drop events on the drop area.
        if obj is self.drop_area and event.type() == QEvent.DragEnter:
            mime_data = event.mimeData()
            if mime_data.hasUrls() and len(mime_data.urls()) == 1 and mime_data.urls()[0].isLocalFile():
                event.acceptProposedAction()
        elif obj is self.drop_area and event.type() == QEvent.Drop:
            mime_data = event.mimeData()
            if mime_data.hasUrls() and len(mime_data.urls()) == 1 and mime_data.urls()[0].isLocalFile():
                image_path = mime_data.urls()[0].toLocalFile()
                self.decodeQRCodeFromImage(image_path)
                event.acceptProposedAction()
        return super().eventFilter(obj, event)


    def update_frame(self):
        if not self.cap or not self.cap.isOpened():
            return 
        if not self.pause_video:
            ret, frame = self.cap.read()  # Read a frame from the camera
            if ret:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = frame_rgb.shape
                bytes_per_line = ch * w
                q_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(q_image)
                self.video_label.setPixmap(pixmap)

                decoded_objects = decode(frame)
                if decoded_objects:
                    self.pause_video = True
                    for obj in decoded_objects:
                        data = obj.data.decode('utf-8')
                        self.showResult(f"Decoded QR Code: {data}")
                        clipboard = QApplication.clipboard()
                        clipboard.setText(data, mode=QClipboard.Clipboard)

                        if data.startswith("WIFI:S:"):
                            ssid, password = extract_wifi_info(data)
                            self.showResult(f"SSID: {ssid}\nPassword: {password}\nPassword copied to clipboard.")
                            clipboard = QApplication.clipboard()
                            clipboard.setText(password, mode=QClipboard.Clipboard)

    def decodeQRCodeFromImage(self, image_path):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly

        if image_path:
            self.pause_video = True
            decode_qrcode(image_path, self)
            self.pause_button.setEnabled(False)
            self.resume_button.setEnabled(True)
        else:
            self.showResult("No QR Code detected.")

    def showResult(self, result):
        self.result_label.setText(result)

    def pauseVideo(self):
        self.pause_video = True
        self.pause_button.setEnabled(False)
        self.resume_button.setEnabled(True)

    def resumeVideo(self):
        self.pause_video = False
        self.pause_button.setEnabled(True)
        self.resume_button.setEnabled(False)

        if self.cap is None:
            self.choose_option_button.setEnabled(True)

    def generateQRCode(self):
        # Get data from the input area
        data = self.encode_input.toPlainText()
        if data:
            # Specify the folder to save the generated QR codes
            save_folder = 'generated_qr_images'
            os.makedirs(save_folder, exist_ok=True)  # Create the folder if it doesn't exist

            # Generate unique file name using the counter
            file_name = f'QRcode_{self.qr_code_counter}.png'
            file_path = os.path.join(save_folder, file_name)

            # Increment the counter for the next QR code
            self.qr_code_counter += 1

            # Generate and save the QR code
            generate_qrcode(data, file_name=file_path)

            # Display the generated picture
            pixmap = QPixmap(file_path)
            self.generated_picture_label.setPixmap(pixmap)
            self.showResult("")

            # Show the copy button after image generation
            self.copy_button.show()

    def copyImage(self):
        pixmap = self.generated_picture_label.pixmap()
        if pixmap:
            clipboard = QApplication.clipboard()
            clipboard.setPixmap(pixmap)
            self.showResult("Image copied to clipboard.")
    
    def showErrorMessage(self, message):
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Error")
        msg_box.setText(message)
        msg_box.exec_()

    def quitApp(self):
        try:
            if self.cap is not None:
                self.cap.release()

            # Delete the temporary directory and its contents
            if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
                import shutil
                shutil.rmtree(self.temp_dir)

            self.close()
        except Exception as e:
            print(f"An error occurred during cleanup: {e}")
        finally:
            self.video_processing_thread.requestInterruption()
            self.video_processing_thread.wait(3000)  # Wait for the thread to finish for up to 3 seconds

def generate_qrcode(data, file_name='qrcode.png'):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(file_name)

def extract_wifi_info(data):
    ssid_start = data.find("WIFI:S:") + len("WIFI:S:")
    ssid_end = data.find(";", ssid_start)
    ssid = data[ssid_start:ssid_end]

    password_start = data.find("T:WPA;P:") + len("T:WPA;P:")
    password_end = data.find(";", password_start)
    password = data[password_start:password_end]

    return ssid, password

def decode_qrcode(image_path, widget):
    image = Image.open(image_path)
    decoded_objects = decode(image)

    if decoded_objects:
        for obj in decoded_objects:
            data = obj.data.decode('utf-8')
            widget.showResult(f"Decoded QR Code: {data}\nData copied to clipboard.")
            clipboard = QApplication.clipboard()
            clipboard.setText(data, mode=QClipboard.Clipboard)

            if data.startswith("WIFI:S:"):
                ssid, password = extract_wifi_info(data)
                widget.showResult(f"SSID: {ssid}\nPassword: {password}\nPassword copied to clipboard.")
                # Automatically copy the password to the clipboard
                clipboard = QApplication.clipboard()
                clipboard.setText(password, mode=QClipboard.Clipboard)

    else:
        widget.showResult("No QR Code detected.")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = QRCodeGeneratorDecoder()
    ex.setWindowIcon(QIcon(resource_path(r'/path/icon.ico')))  # Replace 'app_icon.png' with your icon file 
    ex.show()
    sys.exit(app.exec_())