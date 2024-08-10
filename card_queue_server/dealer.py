import json
import sys
import socket
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QRect
from PyQt6.QtGui import QFont, QFontDatabase


class ServerCheckThread(QThread):
    status_changed = pyqtSignal(bool)

    def __init__(self, server_ip, server_port):
        super().__init__()
        self.server_ip = server_ip
        self.server_port = server_port
        self.running = True

    def run(self):
        while self.running:
            try:
                with socket.create_connection((self.server_ip, self.server_port), timeout=2):
                    self.status_changed.emit(True)
            except Exception:
                self.status_changed.emit(False)
            QThread.sleep(5)  # 5초마다 상태 확인

    def stop(self):
        self.running = False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        myfont = QFontDatabase
        self.futura_id = myfont.addApplicationFont("FuturaWindows_edit.ttf")  # TTF 파일의 경로
        self.futura_family = myfont.applicationFontFamilies(self.futura_id)[0]  # 폰트 패밀리 이름 얻기

        # 폰트 설정
        #font_futura= QFont(futura_family, 12)  # 폰트 패밀리와 크기 설정
        self.server_ip = 'pythontopumj.xyz'
        self.server_port = 9999  # 서버 포트 업데이트
        self.current_action = 'queue'  # 초기 상태: 큐 신청

        self.setWindowTitle('Card Game Client')
        self.setGeometry(100, 100, 400, 200)
        self.setStyleSheet("background-color: #1E1F22;")
        self.card_deck=[]
        self.initUI()
        self.show()

    def initUI(self):
        self.main_layout = QVBoxLayout()

        # Image area
        self.image_label = QLabel('image area', self)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(300, 200)
        self.image_label.setStyleSheet("background-color: #292B2F; color: #CCCCCC; border: 2px solid #CCCCCC;")
        self.main_layout.addWidget(self.image_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Nickname input
        self.nickname_input = QLineEdit(self)
        self.nickname_input.setFixedSize(380, 30)
        self.nickname_input.setPlaceholderText("username")
        self.nickname_input.setStyleSheet("background-color: #CCCCCC; color: black; padding: 5px;")
        self.nickname_input.returnPressed.connect(self.register_nickname)
        self.main_layout.addWidget(self.nickname_input, alignment=Qt.AlignmentFlag.AlignCenter)

        # Error message
        self.error_message = QLabel('', self)
        self.error_message.setStyleSheet("color: red;")
        self.main_layout.addWidget(self.error_message, alignment=Qt.AlignmentFlag.AlignLeft)

        # Server status
        self.status_layout = QHBoxLayout()
        self.status_led = QLabel(self)
        self.status_led.setFixedSize(10, 10)
        self.status_text = QLabel('Offline', self)  # 올바르게 정의된 QLabel
        self.status_text.setStyleSheet("color: red;")
        self.status_layout.addWidget(self.status_led)
        self.status_layout.addWidget(self.status_text)
        self.main_layout.addLayout(self.status_layout)

        # 디버깅 메시지를 표시할 레이블
        self.debug_message_label = QLabel('', self)
        self.debug_message_label.setStyleSheet("color: yellow;")
        self.main_layout.addWidget(self.debug_message_label, alignment=Qt.AlignmentFlag.AlignLeft)

        # Central widget
        self.central_widget = QWidget()
        self.central_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.central_widget)

        # Check server status in a separate thread
        self.server_check_thread = ServerCheckThread(self.server_ip, self.server_port)
        self.server_check_thread.status_changed.connect(self.update_status_led)
        self.server_check_thread.start()

    def send_request(self, request):
        """서버에 요청을 보내고 응답을 받습니다."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                client_socket.connect((self.server_ip, self.server_port))
                client_socket.send(request.encode('utf-8'))
                response = client_socket.recv(4096).decode('utf-8')
                return response
        except Exception as e:
            return f'Error: {e}'

    def register_nickname(self):
        nickname = self.nickname_input.text()
        if not nickname:
            self.error_message.setText('사용자명을 입력해야 합니다.')
            return
        if len(nickname)>10:
            self.error_message.setText('너무 긴 사용자명 입니다.')
            return

        request = json.dumps({'action': 'register', 'nickname': nickname})
        response = self.send_request(request)

        if 'success' in response:
            self.error_message.setText('')
            self.nickname_input.setVisible(False)
            self.error_message.setVisible(False)
            self.transition_to_main_ui()  # 로그인 성공 후 메인 UI로 전환
        else:
            self.error_message.setText(response)

        self.debug_message_label.setText(f"Received: {response}")

    def queue_card(self, card_id, nickname):
        """카드를 서버에서 제거합니다."""
        request = json.dumps({'action': 'claim_queue', 'nickname': nickname})
        response = self.send_request(request)
        self.debug_message_label.setText(f"Remove card response: {response}")
        return response

    def return_card(self, card_id, nickname):
        """카드를 서버에 반납합니다."""
        request = json.dumps({'action': 'return', 'card_id': card_id, 'nickname': nickname})
        response = self.send_request(request)
        self.debug_message_label.setText(f"Return card response: {response}")
        return response

    def update_status_led(self, status):
        color = 'green' if status else 'red'
        self.status_led.setStyleSheet(f"background-color: {color};")
        self.status_text.setText('Online' if status else 'Offline')
        self.status_text.setStyleSheet(f"color: {color};")

    def transition_to_main_ui(self):
        # 창 크기 및 위치 조정
        self.setGeometry(QRect(self.geometry().right() - 250, self.geometry().bottom() - 150, 250, 150))

        # 상단 이미지 및 정보 표시
        self.image_label.setFixedSize(200, 50)
        self.image_label.setText("Status Image Here")  # Placeholder for the status image

        self.info_label = QLabel('Some Information', self)
        self.info_label.setStyleSheet("color: #CCCCCC;")
        self.main_layout.addWidget(self.info_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 하단에 하나의 버튼 추가
        self.action_button = QPushButton("Queue", self)
        self.action_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #CCCCCC;
                color: black;
                font-size: 16px;
                font-family: "{self.futura_family}";
            }}
            QPushButton:disabled {{
                color: gray;
                font-size: 16px;
                font-family: "{self.futura_family}";
            }}
        """)
        self.action_button.setFixedSize(100, 30)
        self.action_button.clicked.connect(self.handle_action)
        self.main_layout.addWidget(self.action_button, alignment=Qt.AlignmentFlag.AlignCenter)

    def handle_action(self):
        nickname = self.nickname_input.text()
        if self.current_action == 'queue':
            self.action_button.setEnabled(False)
            # Queue 관련 기능 구현
            response=self.apply_queue(nickname)
            QTimer.singleShot(5000, lambda: self.action_button.setEnabled(True))
            if 'error' in response:
                self.debug_message_label.setText(f"Return card response: {response}")
            else:
                self.current_action = 'return'
                self.action_button.setText('Return Card')
        else:
            self.action_button.setEnabled(False)
            # Return 관련 기능 구현
            response=self.return_card('some_card_id', nickname)  # 여기에서 적절한 card_id를 사용하도록 수정 필요
            QTimer.singleShot(5000, lambda: self.action_button.setEnabled(True))
            if 'error' in response:
                self.debug_message_label.setText(f"Return card response: {response}")
            else:
                self.current_action = 'queue'
                self.action_button.setText('Queue')

    def apply_queue(self, nickname):
        """큐를 신청합니다."""
        request = json.dumps({'action': 'remove', 'nickname': nickname})
        response = self.send_request(request)
        self.debug_message_label.setText(f"Queue application response: {response}")
        return response


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = MainWindow()
    sys.exit(app.exec())
