import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

from PyQt5 import QtCore, QtNetwork, QtWidgets, uic
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QPixmap
from PyQt5.QtWebEngineWidgets import QWebEngineView

from local_services import ImageSearchWorker, OllamaWorker
from search_providers import (
    ENGINES,
    LANGUAGES,
    build_result_script,
    build_search_url,
    is_web_address,
    parse_search_results,
)


UI_FILE = Path(__file__).with_name("QT File.ui")
THEMES = {
    "high_contrast": {
        "label": "Contraste élevé",
        "background": "#000000",
        "surface": "#0b0b0b",
        "foreground": "#ffffff",
        "secondary": "#d0d0d0",
        "border": "#6fc3df",
        "link": "#75beff",
        "accent": "#f38518",
        "green": "#89d185",
    },
    "dark": {
        "label": "Sombre",
        "background": "#1e1e1e",
        "surface": "#252526",
        "foreground": "#eeeeee",
        "secondary": "#bdbdbd",
        "border": "#555555",
        "link": "#9cdcfe",
        "accent": "#569cd6",
        "green": "#a5d6a7",
    },
    "light": {
        "label": "Clair",
        "background": "#f5f5f5",
        "surface": "#ffffff",
        "foreground": "#1f1f1f",
        "secondary": "#555555",
        "border": "#b7b7b7",
        "link": "#0759a5",
        "accent": "#005fb8",
        "green": "#216e39",
    },
}


class PreferencesDialog(QtWidgets.QDialog):
    def __init__(self, language: str, theme: str, model: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Paramètres")
        self.setMinimumWidth(420)
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()

        self.languageCombo = QtWidgets.QComboBox()
        for label, (code, _country) in LANGUAGES.items():
            self.languageCombo.addItem(label, code)
        language_index = self.languageCombo.findData(language)
        self.languageCombo.setCurrentIndex(max(0, language_index))

        self.themeCombo = QtWidgets.QComboBox()
        for key, details in THEMES.items():
            self.themeCombo.addItem(details["label"], key)
        theme_index = self.themeCombo.findData(theme)
        self.themeCombo.setCurrentIndex(max(0, theme_index))

        self.modelInput = QtWidgets.QLineEdit(model)
        self.modelInput.setPlaceholderText("qwen2.5:3b")
        self.modelStatus = QtWidgets.QLabel(
            "L’assistant IA fonctionne uniquement si Ollama est installé."
        )
        self.modelStatus.setWordWrap(True)
        self.refreshModelsButton = QtWidgets.QPushButton("Détecter mes modèles")

        model_row = QtWidgets.QHBoxLayout()
        model_row.addWidget(self.modelInput, 1)
        model_row.addWidget(self.refreshModelsButton)

        form.addRow("Langue des résultats :", self.languageCombo)
        form.addRow("Thème :", self.themeCombo)
        form.addRow("Modèle IA Ollama :", model_row)
        form.addRow("", self.modelStatus)
        layout.addLayout(form)

        self.helpText = QtWidgets.QLabel(
            "Ollama : installez un modèle avec "
            "<code>ollama pull qwen2.5:3b</code>, puis vérifiez-le ici."
        )
        self.helpText.setWordWrap(True)
        layout.addWidget(self.helpText)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class HistoryDialog(QtWidgets.QDialog):
    def __init__(self, entries, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Historique des recherches")
        self.setMinimumSize(500, 380)
        self.selected_entry = None

        layout = QtWidgets.QVBoxLayout(self)
        self.historyList = QtWidgets.QListWidget()
        for entry in entries:
            item = QtWidgets.QListWidgetItem(
                f'{entry["query"]}   ·   {entry["engine"]}'
            )
            item.setData(QtCore.Qt.UserRole, entry)
            self.historyList.addItem(item)
        if not entries:
            self.historyList.addItem("Aucune recherche enregistrée.")
            self.historyList.item(0).setFlags(QtCore.Qt.NoItemFlags)
        layout.addWidget(self.historyList)

        actions = QtWidgets.QHBoxLayout()
        self.searchButton = QtWidgets.QPushButton("Rechercher")
        self.clearButton = QtWidgets.QPushButton("Effacer l’historique")
        close_button = QtWidgets.QPushButton("Fermer")
        actions.addWidget(self.searchButton)
        actions.addWidget(self.clearButton)
        actions.addStretch(1)
        actions.addWidget(close_button)
        layout.addLayout(actions)

        self.searchButton.clicked.connect(self._select_entry)
        self.historyList.itemDoubleClicked.connect(
            lambda _item: self._select_entry()
        )
        self.clearButton.clicked.connect(self._clear_history)
        close_button.clicked.connect(self.reject)

    def _select_entry(self):
        item = self.historyList.currentItem()
        if item is None:
            return
        entry = item.data(QtCore.Qt.UserRole)
        if entry is not None:
            self.selected_entry = entry
            self.accept()

    def _clear_history(self):
        self.historyList.clear()
        self.selected_entry = None
        self.historyList.addItem("Aucune recherche enregistrée.")
        self.historyList.item(0).setFlags(QtCore.Qt.NoItemFlags)


class SearchApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi(str(UI_FILE), self)
        self.setWindowTitle("Adogle")
        self.setMinimumSize(820, 600)

        self.settings = QtCore.QSettings("Adogle", "Adogle")
        self.engine = self.settings.value("search/engine", "Google")
        if self.engine not in ENGINES:
            self.engine = "Google"
        self.language = self.settings.value("search/language", "fr")
        valid_languages = {code for code, _country in LANGUAGES.values()}
        if self.language not in valid_languages:
            self.language = "fr"
        self.theme = self.settings.value("appearance/theme", "high_contrast")
        if self.theme not in THEMES:
            self.theme = "high_contrast"
        self.ollama_model = self.settings.value(
            "assistant/ollama_model", "qwen2.5:3b"
        )

        self._active_query = ""
        self._active_engine = self.engine
        self._active_results = []
        self._active_images = []
        self._search_serial = 0
        self._image_worker = None
        self._ai_worker = None
        self._workers = set()
        self._image_replies = {}
        self._image_serial = 0
        self._image_worker_query = ""

        self._configure_theme()
        self.browser = QWebEngineView(self)
        self.searchBrowser = QWebEngineView(self)
        self.mainStack.addWidget(self.searchBrowser)
        self.mainStack.addWidget(self.browser)

        self._setup_result_views()
        self._setup_search_engine_controls()
        self._setup_header_controls()
        self._setup_ai_panel()

        self.imageNetwork = QtNetwork.QNetworkAccessManager(self)

        self.backButton.clicked.connect(self.go_back)
        self.forwardButton.clicked.connect(self.browser.forward)
        self.reloadButton.clicked.connect(self.reload_current_page)
        self.homeButton.clicked.connect(self.open_home)
        self.addressBar.returnPressed.connect(self.navigate)
        self.topGoButton.clicked.connect(self.navigate)
        self.homeSearch.returnPressed.connect(self.search_from_home)
        self.homeSearchButton.clicked.connect(self.search_from_home)
        self.resultsSearch.returnPressed.connect(self.search_from_results)
        self.resultsSearchButton.clicked.connect(self.search_from_results)
        self.webTabButton.clicked.connect(self.show_web_results)
        self.imagesTabButton.clicked.connect(self.search_images)
        self.aiTabButton.clicked.connect(self.show_ai_panel)
        self.historyButton.clicked.connect(self.open_history)
        self.preferencesButton.clicked.connect(self.open_preferences)

        self.browser.urlChanged.connect(self.update_address)
        self.browser.urlChanged.connect(self.update_navigation_buttons)
        self.browser.loadFinished.connect(self.update_navigation_buttons)
        self.browser.loadStarted.connect(
            lambda: self.statusbar.showMessage("Chargement de la page…")
        )
        self.browser.loadFinished.connect(self.browser_load_finished)
        self.searchBrowser.loadFinished.connect(self.search_load_finished)

        self.homeSearch.setFocus()
        self.update_navigation_buttons()

    def _configure_theme(self):
        colors = THEMES[self.theme]
        self.setStyleSheet(
            f"""
            QMainWindow, QWidget {{
                background-color: {colors["background"]};
                color: {colors["foreground"]};
                font-family: "Segoe UI";
                font-size: 10pt;
            }}
            QToolBar {{
                background-color: {colors["background"]};
                border: 0;
                border-bottom: 1px solid {colors["border"]};
                spacing: 6px;
                padding: 7px;
            }}
            QToolButton, QPushButton, QComboBox {{
                background-color: {colors["surface"]};
                color: {colors["foreground"]};
                border: 1px solid {colors["border"]};
                border-radius: 5px;
                padding: 7px 12px;
                min-height: 24px;
            }}
            QToolButton:hover, QPushButton:hover {{
                background-color: {colors["accent"]};
                border-color: {colors["foreground"]};
            }}
            QToolButton:disabled {{
                color: {colors["secondary"]};
                border-color: {colors["border"]};
            }}
            QLineEdit, QPlainTextEdit {{
                background-color: {colors["surface"]};
                color: {colors["foreground"]};
                border: 1px solid {colors["border"]};
                border-radius: 6px;
                padding: 9px 12px;
                selection-background-color: {colors["accent"]};
                min-height: 24px;
            }}
            QLineEdit:focus {{
                border: 2px solid {colors["accent"]};
            }}
            QComboBox::drop-down {{
                border: 0;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors["surface"]};
                color: {colors["foreground"]};
                selection-background-color: {colors["accent"]};
            }}
            QScrollArea {{
                border: 0;
                background-color: {colors["background"]};
            }}
            QFrame[resultCard="true"] {{
                background-color: {colors["surface"]};
                border: 1px solid {colors["border"]};
                border-radius: 7px;
            }}
            QStatusBar {{
                background-color: {colors["background"]};
                color: {colors["secondary"]};
                border-top: 1px solid {colors["border"]};
            }}
            """
        )

    def _setup_search_engine_controls(self):
        self.homeEngineCombo = QtWidgets.QComboBox(self.homePage)
        self.resultsEngineCombo = QtWidgets.QComboBox(self.resultsPage)
        for combo in (self.homeEngineCombo, self.resultsEngineCombo):
            combo.addItems(ENGINES)
            combo.setCurrentText(self.engine)
            combo.setMinimumWidth(125)
            combo.setToolTip("Choisir le moteur de recherche")
        self.homeSearchLayout.insertWidget(1, self.homeEngineCombo)
        self.resultsSearchLayout.insertWidget(2, self.resultsEngineCombo)
        self.homeEngineCombo.currentTextChanged.connect(
            self._search_engine_changed
        )
        self.resultsEngineCombo.currentTextChanged.connect(
            self._search_engine_changed
        )

    def _setup_header_controls(self):
        self.historyButton = QtWidgets.QPushButton("Historique", self)
        self.historyButton.setToolTip("Afficher les recherches récentes")
        self.preferencesButton = QtWidgets.QPushButton("Paramètres", self)
        navigation_layout = self.findChild(
            QtWidgets.QHBoxLayout, "navigationLayout"
        )
        navigation_layout.addWidget(self.historyButton)
        navigation_layout.addWidget(self.preferencesButton)

    def _setup_result_views(self):
        self.resultsPage.layout().removeWidget(self.resultsScrollArea)
        self.resultViews = QtWidgets.QStackedWidget(self.resultsPage)
        self.resultsPage.layout().addWidget(self.resultViews, 1)
        self.resultViews.addWidget(self.resultsScrollArea)
        self.webResultsView = self.resultsScrollArea

        self.imagesScrollArea = QtWidgets.QScrollArea(self.resultsPage)
        self.imagesScrollArea.setWidgetResizable(True)
        self.imagesContents = QtWidgets.QWidget()
        self.imagesGridLayout = QtWidgets.QGridLayout(self.imagesContents)
        self.imagesGridLayout.setSpacing(14)
        self.imagesScrollArea.setWidget(self.imagesContents)
        self.resultViews.addWidget(self.imagesScrollArea)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setSpacing(8)
        self.webTabButton = QtWidgets.QPushButton("Web")
        self.imagesTabButton = QtWidgets.QPushButton("Images")
        self.aiTabButton = QtWidgets.QPushButton("Assistant IA")
        self.webTabButton.setCheckable(True)
        self.imagesTabButton.setCheckable(True)
        self.aiTabButton.setCheckable(True)
        self.webTabButton.setChecked(True)
        toolbar.addWidget(self.webTabButton)
        toolbar.addWidget(self.imagesTabButton)
        toolbar.addWidget(self.aiTabButton)
        toolbar.addStretch(1)
        self.resultsPage.layout().insertLayout(3, toolbar)

    def _setup_ai_panel(self):
        self.aiPage = QtWidgets.QWidget(self.resultsPage)
        layout = QtWidgets.QVBoxLayout(self.aiPage)
        layout.setContentsMargins(8, 8, 8, 8)

        self.aiStatus = QtWidgets.QLabel(
            "Réponses générées par votre modèle Ollama local."
        )
        self.aiStatus.setWordWrap(True)
        layout.addWidget(self.aiStatus)

        self.aiAnswer = QtWidgets.QPlainTextEdit()
        self.aiAnswer.setReadOnly(True)
        self.aiAnswer.setPlaceholderText(
            "Demandez un résumé ou posez une question sur les résultats."
        )
        layout.addWidget(self.aiAnswer, 1)

        ask_row = QtWidgets.QHBoxLayout()
        self.aiQuestion = QtWidgets.QLineEdit()
        self.aiQuestion.setPlaceholderText(
            "Résume ces résultats ou pose une question…"
        )
        self.aiQuestion.setText("Résume les résultats")
        self.aiAskButton = QtWidgets.QPushButton("Demander")
        self.downloadOllamaButton = QtWidgets.QPushButton("Installer Ollama")
        ask_row.addWidget(self.aiQuestion, 1)
        ask_row.addWidget(self.aiAskButton)
        ask_row.addWidget(self.downloadOllamaButton)
        layout.addLayout(ask_row)

        self.resultViews.addWidget(self.aiPage)
        self.aiAskButton.clicked.connect(self.ask_ai)
        self.aiQuestion.returnPressed.connect(self.ask_ai)
        self.downloadOllamaButton.clicked.connect(
            lambda: self.open_web_page("https://ollama.com/download")
        )

    def _search_engine_changed(self, engine: str):
        if engine not in ENGINES:
            return
        self.engine = engine
        self.settings.setValue("search/engine", engine)
        for combo in (self.homeEngineCombo, self.resultsEngineCombo):
            if combo.currentText() != engine:
                combo.blockSignals(True)
                combo.setCurrentText(engine)
                combo.blockSignals(False)

    def search_from_home(self):
        self.start_search(self.homeSearch.text(), self.homeEngineCombo.currentText())

    def search_from_results(self):
        self.start_search(
            self.resultsSearch.text(), self.resultsEngineCombo.currentText()
        )

    def start_search(self, text: str, engine: str | None = None):
        query = text.strip()
        if not query:
            self.homeSearch.setFocus()
            return

        if is_web_address(query):
            if "://" not in query and not query.startswith("//"):
                query = "https://" + query
            elif query.startswith("//"):
                query = "https:" + query
            self.open_web_page(query)
            return

        selected_engine = engine if engine in ENGINES else self.engine
        self._search_engine_changed(selected_engine)
        address = build_search_url(query, selected_engine, self.language)

        self.searchBrowser.stop()
        self._search_serial += 1
        self._expected_search_url = address
        self._active_query = query
        self._active_engine = selected_engine
        self._active_results = []
        self.resultsSearch.setText(query)
        self.queryTitle.setText(f"Résultats pour « {query} »")
        self.resultCount.clear()
        self._save_history(query, selected_engine)
        self._show_message("Recherche en cours…")
        self._show_result_tab(self.webResultsView)
        self.mainStack.setCurrentWidget(self.resultsPage)
        self.statusbar.showMessage(f"Recherche sur {selected_engine}…")
        self.searchBrowser.setUrl(QUrl(address))

    def search_load_finished(self, succeeded: bool):
        serial = self._search_serial
        if not succeeded:
            if self.searchBrowser.url().toString() == self._expected_search_url:
                self._show_search_error(
                    f"Impossible de joindre {self._active_engine}. "
                    "Vérifiez votre connexion ou essayez un autre moteur."
                )
            return
        self._extract_search_results(serial)

    def _extract_search_results(self, serial: int, attempt: int = 0):
        if serial != self._search_serial:
            return
        script = build_result_script(self._active_engine)
        self.searchBrowser.page().runJavaScript(
            script,
            lambda payload: self.show_search_results(
                payload, serial, attempt
            ),
        )

    def show_search_results(self, payload, serial, attempt: int = 0):
        if serial != self._search_serial:
            return
        try:
            items = json.loads(payload) if isinstance(payload, str) else payload
            results = parse_search_results(items)
        except (json.JSONDecodeError, TypeError, ValueError):
            results = []

        if not results:
            if attempt < 2:
                QtCore.QTimer.singleShot(
                    800,
                    lambda: self._extract_search_results(serial, attempt + 1),
                )
                return
            self._show_search_error(
                f"Aucun résultat extractible depuis {self._active_engine}. "
                "Réessayez ou choisissez un autre moteur."
            )
            return

        self._active_results = results
        self._render_web_results()
        label = "résultat" if len(results) == 1 else "résultats"
        self.resultCount.setText(f"{len(results)} {label} · {self._active_engine}")
        self.statusbar.showMessage(f"{len(results)} {label} trouvés.", 4000)
        self._show_result_tab(self.webResultsView)
        self.mainStack.setCurrentWidget(self.resultsPage)

    def _render_web_results(self):
        self._clear_results()
        for title, url, snippet in self._active_results:
            self._add_result_card(title, url, snippet)
        self.resultsLayout.addStretch(1)

    def _add_result_card(self, title: str, url: str, snippet: str):
        colors = THEMES[self.theme]
        card = QtWidgets.QFrame()
        card.setProperty("resultCard", True)
        card.setStyleSheet(
            "QFrame[resultCard='true'] { "
            f"background: {colors['surface']}; "
            f"border: 1px solid {colors['border']}; "
            "border-radius: 7px; }"
        )
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(16, 13, 16, 13)
        layout.setSpacing(6)

        title_button = QtWidgets.QPushButton(title)
        title_button.setCursor(QtCore.Qt.PointingHandCursor)
        title_button.setStyleSheet(
            "QPushButton { "
            f"color: {colors['link']}; "
            "text-align: left; font-size: 12pt; font-weight: 600; "
            "border: 0; padding: 0; background: transparent; }"
            "QPushButton:hover { color: "
            f"{colors['foreground']}; background: transparent; "
            "text-decoration: underline; }"
        )
        title_button.clicked.connect(
            lambda _checked=False, target=url: self.open_web_page(target)
        )

        address = QtWidgets.QLabel(url)
        address.setTextFormat(QtCore.Qt.PlainText)
        address.setWordWrap(True)
        address.setStyleSheet(
            "QLabel { "
            f"color: {colors['green']}; "
            "font-size: 9pt; border: 0; }"
        )

        layout.addWidget(title_button)
        layout.addWidget(address)
        if snippet:
            description = QtWidgets.QLabel(snippet)
            description.setTextFormat(QtCore.Qt.PlainText)
            description.setWordWrap(True)
            description.setStyleSheet(
                "QLabel { "
                f"color: {colors['foreground']}; "
                "border: 0; }"
            )
            layout.addWidget(description)
        self.resultsLayout.addWidget(card)

    def _clear_results(self):
        while self.resultsLayout.count():
            item = self.resultsLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _show_message(self, message: str):
        self._clear_results()
        label = QtWidgets.QLabel(message)
        label.setWordWrap(True)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setStyleSheet(
            f"color: {THEMES[self.theme]['secondary']}; padding: 32px;"
        )
        self.resultsLayout.addWidget(label)
        self.resultsLayout.addStretch(1)

    def _show_search_error(self, message: str):
        self._show_message(message)
        retry_button = QtWidgets.QPushButton("Réessayer")
        retry_button.clicked.connect(self.search_from_results)
        self.resultsLayout.insertWidget(
            1, retry_button, 0, QtCore.Qt.AlignHCenter
        )
        self.statusbar.showMessage(message, 6000)

    def _show_result_tab(self, widget: QtWidgets.QWidget):
        self.resultViews.setCurrentWidget(widget)
        self.webTabButton.setChecked(widget is self.webResultsView)
        self.imagesTabButton.setChecked(widget is self.imagesScrollArea)
        self.aiTabButton.setChecked(widget is self.aiPage)

    def show_web_results(self):
        self._show_result_tab(self.webResultsView)

    def search_images(self):
        if not self._active_query:
            self.statusbar.showMessage("Effectuez d’abord une recherche.", 4000)
            return
        if (
            self._image_worker is not None
            and self._image_worker.isRunning()
            and self._image_worker_query == self._active_query
        ):
            self._show_result_tab(self.imagesScrollArea)
            return
        self._show_result_tab(self.imagesScrollArea)
        self._image_serial += 1
        self._active_images = []
        self._show_image_message("Recherche d’images libres…")
        worker = ImageSearchWorker(
            self._active_query, self.language, parent=self
        )
        self._image_worker = worker
        self._image_worker_query = self._active_query
        worker.succeeded.connect(
            lambda images, serial=self._image_serial: self._show_images(
                images, serial
            )
        )
        worker.failed.connect(self._show_image_error)
        self._start_worker(worker)

    def _show_image_message(self, message: str):
        self._clear_image_grid()
        if not message:
            return
        label = QtWidgets.QLabel(message)
        label.setWordWrap(True)
        self.imagesGridLayout.addWidget(label, 0, 0, 1, 3)

    def _clear_image_grid(self):
        for reply in list(self._image_replies):
            try:
                reply.finished.disconnect()
            except TypeError:
                pass
            reply.abort()
            reply.deleteLater()
        self._image_replies.clear()
        while self.imagesGridLayout.count():
            item = self.imagesGridLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _show_images(self, images, serial: int):
        if serial != self._image_serial:
            return
        self._active_images = images
        self._clear_image_grid()
        if not images:
            self._show_image_message(
                "Aucune image libre trouvée dans Wikimedia Commons."
            )
            return
        for index, image in enumerate(images):
            row, column = divmod(index, 3)
            self.imagesGridLayout.addWidget(
                self._create_image_card(image), row, column
            )
        self.imagesGridLayout.setRowStretch((len(images) + 2) // 3, 1)
        self.statusbar.showMessage(
            f'{len(images)} images libres trouvées · Wikimedia Commons', 5000
        )

    def _create_image_card(self, image: dict) -> QtWidgets.QWidget:
        colors = THEMES[self.theme]
        card = QtWidgets.QFrame()
        card.setProperty("resultCard", True)
        card.setStyleSheet(
            "QFrame[resultCard='true'] { "
            f"background: {colors['surface']}; "
            f"border: 1px solid {colors['border']}; "
            "border-radius: 7px; }"
        )
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        preview = QtWidgets.QLabel("Chargement de l’image…")
        preview.setAlignment(QtCore.Qt.AlignCenter)
        preview.setFixedSize(220, 150)
        preview.setWordWrap(True)
        layout.addWidget(preview, 0, QtCore.Qt.AlignHCenter)

        title = QtWidgets.QPushButton(image["title"])
        title.setCursor(QtCore.Qt.PointingHandCursor)
        title.setToolTip("Ouvrir la page de cette image")
        title.setStyleSheet(
            "QPushButton { "
            f"color: {colors['link']}; "
            "text-align: left; border: 0; background: transparent; }"
        )
        title.clicked.connect(
            lambda _checked=False, url=image["page_url"]: self.open_web_page(
                url
            )
        )
        layout.addWidget(title)

        credit = " · ".join(
            value
            for value in (image.get("attribution"), image.get("license"))
            if value
        )
        if credit:
            attribution = QtWidgets.QLabel(credit)
            attribution.setWordWrap(True)
            attribution.setStyleSheet(
                f"color: {colors['secondary']}; font-size: 8pt; border: 0;"
            )
            layout.addWidget(attribution)
        if image.get("license_url"):
            license_button = QtWidgets.QPushButton("Licence")
            license_button.setCursor(QtCore.Qt.PointingHandCursor)
            license_button.setStyleSheet(
                "QPushButton { color: "
                f"{colors['link']}; text-align: left; border: 0; "
                "background: transparent; padding: 0; }"
            )
            license_button.clicked.connect(
                lambda _checked=False, url=image["license_url"]: self.open_web_page(
                    url
                )
            )
            layout.addWidget(license_button)

        request = QtNetwork.QNetworkRequest(QUrl(image["thumbnail_url"]))
        request.setRawHeader(b"User-Agent", b"Adogle/1.0")
        reply = self.imageNetwork.get(request)
        reply.finished.connect(
            lambda current=reply, label=preview: self._image_loaded(
                current, label
            )
        )
        self._image_replies[reply] = preview
        return card

    def _image_loaded(
        self, reply: QtNetwork.QNetworkReply, preview: QtWidgets.QLabel
    ):
        self._image_replies.pop(reply, None)
        data = bytes(reply.readAll())
        error = reply.error()
        reply.deleteLater()
        pixmap = QPixmap()
        if error == QtNetwork.QNetworkReply.NoError and pixmap.loadFromData(data):
            preview.setPixmap(
                pixmap.scaled(
                    preview.size(),
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
            )
            preview.setText("")
        else:
            preview.setText("Image indisponible")

    def _show_image_error(self, message: str):
        self._show_image_message(message)
        self.statusbar.showMessage(message, 6000)

    def show_ai_panel(self):
        if not self._active_query or not self._active_results:
            self.statusbar.showMessage(
                "Effectuez une recherche Web avant de demander une réponse à l’IA.",
                5000,
            )
            return
        self._show_result_tab(self.aiPage)

    def ask_ai(self):
        if not self._active_results:
            self.aiStatus.setText(
                "Effectuez d’abord une recherche Web pour fournir des sources."
            )
            return
        if self._ai_worker is not None and self._ai_worker.isRunning():
            self.aiStatus.setText("Une réponse est déjà en cours.")
            return
        question = self.aiQuestion.text().strip() or "Résume les résultats"
        self._show_result_tab(self.aiPage)
        self.aiAnswer.clear()
        self.aiStatus.setText(
            f"Réponse locale en cours avec {self.ollama_model}…"
        )
        self.aiAskButton.setEnabled(False)
        worker = OllamaWorker(
            "answer",
            model=self.ollama_model,
            query=self._active_query,
            results=self._active_results,
            question=question,
            language=self.language,
            parent=self,
        )
        self._ai_worker = worker
        worker.answer_ready.connect(self._show_ai_answer)
        worker.failed.connect(self._show_ai_error)
        self._start_worker(worker)

    def _show_ai_answer(self, answer: str):
        self.aiAnswer.setPlainText(answer)
        self.aiStatus.setText(f"Réponse générée localement · {self.ollama_model}")
        self.statusbar.showMessage("Réponse IA terminée.", 4000)

    def _show_ai_error(self, message: str):
        self.aiStatus.setText(message)
        self.statusbar.showMessage("L’assistant IA est indisponible.", 5000)

    def _start_worker(self, worker: QtCore.QThread):
        self._workers.add(worker)
        worker.finished.connect(
            lambda current=worker: self._worker_finished(current)
        )
        worker.start()

    def _worker_finished(self, worker: QtCore.QThread):
        self._workers.discard(worker)
        if self._image_worker is worker:
            self._image_worker = None
            self._image_worker_query = ""
        if self._ai_worker is worker:
            self._ai_worker = None
            self.aiAskButton.setEnabled(True)

    def _save_history(self, query: str, engine: str):
        entries = self._load_history()
        entry = {"query": query, "engine": engine}
        entries = [
            existing
            for existing in entries
            if existing.get("query") != query
            or existing.get("engine") != engine
        ]
        entries.insert(0, entry)
        self.settings.setValue(
            "search/history", json.dumps(entries[:100], ensure_ascii=False)
        )

    def _load_history(self) -> list[dict]:
        value = self.settings.value("search/history", "[]")
        try:
            entries = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return []
        if not isinstance(entries, list):
            return []
        return [
            entry
            for entry in entries
            if isinstance(entry, dict)
            and isinstance(entry.get("query"), str)
            and entry.get("engine") in ENGINES
        ]

    def open_history(self):
        dialog = HistoryDialog(self._load_history(), self)
        dialog.clearButton.clicked.connect(
            lambda: self.settings.setValue("search/history", "[]")
        )
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            entry = dialog.selected_entry
            if entry is not None:
                combo = (
                    self.homeEngineCombo
                    if self.mainStack.currentWidget() is self.homePage
                    else self.resultsEngineCombo
                )
                combo.setCurrentText(entry["engine"])
                self.homeSearch.setText(entry["query"])
                self.start_search(entry["query"], entry["engine"])

    def open_preferences(self):
        dialog = PreferencesDialog(
            self.language, self.theme, self.ollama_model, self
        )
        dialog.refreshModelsButton.clicked.connect(
            lambda: self.refresh_ollama_models(dialog)
        )
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        self.language = dialog.languageCombo.currentData()
        self.theme = dialog.themeCombo.currentData()
        self.ollama_model = dialog.modelInput.text().strip() or "qwen2.5:3b"
        self.settings.setValue("search/language", self.language)
        self.settings.setValue("appearance/theme", self.theme)
        self.settings.setValue("assistant/ollama_model", self.ollama_model)
        self._configure_theme()
        if self.resultViews.currentWidget() is self.webResultsView:
            self._render_web_results()
        elif self.resultViews.currentWidget() is self.imagesScrollArea:
            self._show_images(self._active_images, self._image_serial)
        self.statusbar.showMessage("Paramètres enregistrés.", 3000)

    def refresh_ollama_models(self, dialog: PreferencesDialog):
        dialog.modelStatus.setText("Recherche des modèles Ollama locaux…")
        worker = OllamaWorker("models", parent=self)
        worker.models_loaded.connect(
            lambda models: self._ollama_models_loaded(dialog, models)
        )
        worker.failed.connect(
            lambda message: dialog.modelStatus.setText(message)
        )
        self._start_worker(worker)

    def _ollama_models_loaded(self, dialog: PreferencesDialog, models):
        if models:
            dialog.modelStatus.setText(
                f"{len(models)} modèle(s) Ollama disponible(s)."
            )
            if dialog.modelInput.text().strip() not in models:
                dialog.modelInput.setText(models[0])
        else:
            dialog.modelStatus.setText(
                "Ollama fonctionne, mais aucun modèle n’est installé. "
                "Utilisez « ollama pull qwen2.5:3b »."
            )

    def open_web_page(self, address: str):
        parsed = urlsplit(address)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            self.statusbar.showMessage("Adresse Web invalide.", 4000)
            return
        self.mainStack.setCurrentWidget(self.browser)
        self.browser.setUrl(QUrl(address))

    def navigate(self):
        self.start_search(
            self.addressBar.text(), self.homeEngineCombo.currentText()
        )

    def open_home(self):
        self.browser.stop()
        self.homeSearch.clear()
        self.mainStack.setCurrentWidget(self.homePage)
        self.homeSearch.setFocus()
        self.statusbar.clearMessage()
        self.update_navigation_buttons()

    def go_back(self):
        if self.mainStack.currentWidget() is self.browser:
            if self.browser.history().canGoBack():
                self.browser.back()
            elif self._active_results:
                self.mainStack.setCurrentWidget(self.resultsPage)
            else:
                self.open_home()
        elif self.mainStack.currentWidget() is self.resultsPage:
            self.open_home()
        else:
            self.homeSearch.setFocus()
        self.update_navigation_buttons()

    def reload_current_page(self):
        if self.mainStack.currentWidget() is self.browser:
            self.browser.reload()
        elif self._active_query:
            self.start_search(self._active_query, self._active_engine)
        else:
            self.homeSearch.setFocus()

    def update_address(self, url: QUrl):
        if not self.addressBar.hasFocus():
            self.addressBar.setText(url.toString())
        self.update_navigation_buttons()

    def browser_load_finished(self, succeeded: bool):
        if succeeded:
            title = self.browser.title()
            self.setWindowTitle(f"{title} — Adogle" if title else "Adogle")
            self.statusbar.clearMessage()
        else:
            self.statusbar.showMessage("Impossible de charger cette page.", 5000)
        self.update_navigation_buttons()

    def update_navigation_buttons(self, *_args):
        on_home = self.mainStack.currentWidget() is self.homePage
        on_results = self.mainStack.currentWidget() is self.resultsPage
        on_browser = self.mainStack.currentWidget() is self.browser
        self.backButton.setEnabled(
            (on_browser and self.browser.history().canGoBack())
            or on_results
            or (on_browser and bool(self._active_results))
        )
        self.forwardButton.setEnabled(
            on_browser and self.browser.history().canGoForward()
        )
        self.reloadButton.setEnabled(not on_home)


if __name__ == "__main__":
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    window = SearchApp()
    window.show()
    sys.exit(app.exec_())
