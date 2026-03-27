import sys
import requests
from PyQt5 import QtWidgets, uic, QtCore

APIKEY = "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"
UI_FILE = "Fichier QT.ui"

class SearchApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi(UI_FILE, self)

        self.lineEdit_2 = self.findChild(QtWidgets.QLineEdit, "lineEdit_2")
        self.pushButton = self.findChild(QtWidgets.QPushButton, "pushButton")
        self.pushButton_2 = self.findChild(QtWidgets.QPushButton, "pushButton_2")
        self.scrollArea = self.findChild(QtWidgets.QScrollArea, "scrollArea")
        self.scroll_widget = self.scrollArea.widget()

        self.verticalLayout_results = QtWidgets.QVBoxLayout(self.scroll_widget)
        self.verticalLayout_results.setSpacing(15)

        self.stackedWidget = self.findChild(QtWidgets.QStackedWidget, "stackedWidget")

        self.setStyleSheet("""
            QWidget {
                background-color: #202124;
                color: white;
            }
            QLineEdit {
                background-color: #303134;
                border-radius: 15px;
                padding: 8px;
                color: white;
            }
            QPushButton {
                background-color: #303134;
                border-radius: 10px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #3c4043;
            }
        """)

        self.lineEdit_2.setPlaceholderText("🔎 Rechercher...")

        self.completer = QtWidgets.QCompleter([
            "python", "qt designer", "api gratuite", "programmation",
            "intelligence artificielle", "robotique", "arduino"
        ])
        self.completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.lineEdit_2.setCompleter(self.completer)

        self.pushButton.clicked.connect(self.do_search)
        self.pushButton_2.clicked.connect(self.go_back)

        self.lineEdit_2.setAlignment(QtCore.Qt.AlignCenter)

    def clear_results(self):
        while self.verticalLayout_results.count():
            item = self.verticalLayout_results.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def add_result(self, title, url, content, delay=0):
        container = QtWidgets.QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: #303134;
                border-radius: 10px;
                padding: 10px;
            }
            QFrame:hover {
                background-color: #3c4043;
            }
        """)

        layout = QtWidgets.QVBoxLayout(container)

        title_label = QtWidgets.QLabel(f"<b>{title}</b>")
        title_label.setStyleSheet("color: #8ab4f8; font-size: 14pt;")
        title_label.setWordWrap(True)

        url_label = QtWidgets.QLabel(f"<a href=\"{url}\">{url}</a>")
        url_label.setOpenExternalLinks(True)
        url_label.setStyleSheet("color: #34a853;")

        content_label = QtWidgets.QLabel(content)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("color: #bdc1c6;")

        layout.addWidget(title_label)
        layout.addWidget(url_label)
        layout.addWidget(content_label)

        container.setGraphicsEffect(QtWidgets.QGraphicsOpacityEffect())
        animation = QtCore.QPropertyAnimation(container.graphicsEffect(), b"opacity")
        animation.setDuration(500)
        animation.setStartValue(0)
        animation.setEndValue(1)

        QtCore.QTimer.singleShot(delay, animation.start)

        self.verticalLayout_results.addWidget(container)

    def do_search(self):
        query_text = self.lineEdit_2.text().strip()
        if not query_text:
            return

        try:
            url = "https://api.tavily.com/search"
            payload = {
                "api_key": APIKEY,
                "query": query_text,
                "search_depth": "basic",
                "max_results": 5
            }
            response = requests.post(url, json=payload)
            data = response.json()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Erreur API", str(e))
            return

        self.clear_results()

        if "results" in data:
            delay = 0
            for r in data["results"]:
                self.add_result(
                    r.get("title", ""),
                    r.get("url", ""),
                    r.get("content", ""),
                    delay
                )
                delay += 120

        self.stackedWidget.setCurrentIndex(1)

    def go_back(self):
        self.stackedWidget.setCurrentIndex(0)
        self.clear_results()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = SearchApp()
    window.show()
    sys.exit(app.exec_())