import copy
from collections.abc import Callable
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import PROJECTS_DIR, USER_DATA_DIR
from app.core.project_io import ProjectIO
from app.core.people_roles import ASSIGNMENT_OPTIONS
from app.gui.document_preview import DocumentPreview
from app.gui.editor_wizard import EditorWizard, page_layout
from app.gui.export_validation import confirm_export
from app.gui.printing import print_project
from app.gui.responsive import ResponsiveActionBar, configure_editable_combo, configure_form, editor_toolbar
from app.core.wol_importer import (
    JW_MEETINGS_BASE_URL,
    WolImportError,
    append_imported_meeting,
    current_week_url,
    fetch_wol_program,
    standard_program_sections,
)
from app.templates.midweek_meeting.default_project import normal_meeting, program_item, section, special_event
from app.templates.midweek_meeting.renderer import numbered_program_title


class MidweekMeetingEditor(QWidget):
    def __init__(
        self,
        project: dict,
        people: list[str],
        renderer_class,
        project_path: Path | None,
        go_back: Callable,
        edit_people: Callable,
        animations_enabled: Callable[[], bool] | None = None,
    ):
        super().__init__()
        self.project = project
        self.project.setdefault("template_id", "midweek_meeting")
        self.project.setdefault("meetings", [])
        self.people = list(people)
        self.renderer = renderer_class
        self.project_path = project_path
        self.animations_enabled = animations_enabled or (lambda: True)
        self.meeting_index = -1
        self.section_index = -1
        self.item_index = -1
        self.person_fields: list[QComboBox] = []
        self.role_people: dict[str, list[str]] = {}
        self.shortcuts: list[QShortcut] = []
        self._build_ui(go_back, edit_people)
        self.refresh_meetings(0)
        self.select_meeting(0)
        self.refresh_preview()

    def _build_ui(self, go_back, edit_people):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        back = QPushButton("← Wróć do menu")
        people = QPushButton("Biblioteka osób")
        previous_meeting = QPushButton("←")
        previous_meeting.setToolTip("Poprzednie zebranie")
        self.meeting_switch = QComboBox()
        self.meeting_switch.setMinimumWidth(0)
        self.meeting_switch.setToolTip("Przełącz edytowane zebranie bez wracania do pierwszego kroku")
        next_meeting = QPushButton("→")
        next_meeting.setToolTip("Następne zebranie")
        save = QPushButton("Zapisz projekt")
        save.setObjectName("primaryButton")
        save_as = QPushButton("Zapisz jako…")
        root.addWidget(editor_toolbar([back, people, save, save_as]), 0)

        context_frame = QWidget()
        context_frame.setObjectName("editorContextBar")
        context = QHBoxLayout(context_frame)
        context.setContentsMargins(12, 7, 12, 7)
        self.context_label = QLabel("Edytowane zebranie:")
        context.addWidget(self.context_label)
        context.addWidget(previous_meeting)
        context.addWidget(self.meeting_switch, 1)
        context.addWidget(next_meeting)
        self.meeting_position = QLabel("Brak zebrań")
        self.meeting_position.setObjectName("helpText")
        context.addWidget(self.meeting_position)
        root.addWidget(context_frame, 0)

        self.wizard = EditorWizard(self.animations_enabled)
        root.addWidget(self.wizard, 1)

        meetings_page = QWidget()
        meetings_layout = page_layout(
            meetings_page,
            "Dokument i lista zebrań",
            "Ustaw nazwę dokumentu oraz zboru, potem dodaj lub wybierz zebranie do edycji.",
        )
        header_group = QGroupBox("Ustawienia dokumentu")
        header = configure_form(QFormLayout(header_group))
        self.document_title = QLineEdit(self.project.get("document_title", "Plan zebrań w tygodniu"))
        self.congregation = QLineEdit(self.project.get("congregation", ""))
        header.addRow("Tytuł dokumentu:", self.document_title)
        header.addRow("Zbór:", self.congregation)
        meetings_layout.addWidget(header_group)

        left = QGroupBox("Zebrania w projekcie")
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self._instruction(
            "Aby dodać wypełnione zebranie, wybierz „Nowy formularz”, uzupełnij krok „Dane” i dodaj je z formularza."
        ))
        self.meeting_list = QListWidget()
        new_form = QPushButton("Nowy formularz")
        new_form.setToolTip("Czyści krok „Dane”, aby przygotować nowe zebranie bez zmieniania wybranego wpisu.")
        add_normal = QPushButton("+ Dodaj zwykłe z formularza")
        add_special = QPushButton("+ Dodaj specjalne z formularza")
        add_normal.setToolTip("Dodaje zwykłe zebranie z informacjami wpisanymi w kroku „Dane”.")
        add_special.setToolTip("Dodaje wydarzenie specjalne z aktualnie wpisanymi informacjami.")
        duplicate = QPushButton("Duplikuj wybrane (+7 dni)")
        duplicate.setToolTip("Kopiuje całe zebranie wraz z programem i ustawia datę tydzień później.")
        delete = QPushButton("Usuń")
        delete.setObjectName("dangerButton")
        up = QPushButton("Przenieś wyżej")
        down = QPushButton("Przenieś niżej")
        left_layout.addWidget(self.meeting_list)
        left_layout.addWidget(
            ResponsiveActionBar([new_form, add_normal, add_special, duplicate, delete, up, down], 145, 2)
        )
        meetings_layout.addWidget(left, 1)

        details_page = QWidget()
        details_layout = page_layout(
            details_page,
            "Dane wybranego zebrania",
            "Uzupełnij datę, osoby oraz rozpoczęcie i zakończenie programu.",
        )
        details_layout.addWidget(self._build_details_tab(), 1)

        content_page = QWidget()
        content_layout = page_layout(
            content_page,
            "Program lub wydarzenie specjalne",
            "Ten krok automatycznie dopasowuje się do typu wybranego zebrania.",
        )
        self.content_stack = QStackedWidget()
        self.program_widget = self._build_program_tab()
        self.special_widget = self._build_special_tab()
        self.content_stack.addWidget(self.program_widget)
        self.content_stack.addWidget(self.special_widget)
        content_layout.addWidget(self.content_stack, 1)

        preview_page = QWidget()
        preview_layout = page_layout(
            preview_page,
            "Podgląd i eksport",
            "Sprawdź cały plan w dużym podglądzie, a następnie wybierz format eksportu.",
        )
        self.preview = DocumentPreview()
        pdf = QPushButton("Eksportuj PDF")
        jpg = QPushButton("Eksportuj JPG")
        both = QPushButton("Eksportuj PDF + JPG")
        print_button = QPushButton("Drukuj")
        both.setObjectName("primaryButton")
        preview_layout.addWidget(self.preview, 1)
        preview_layout.addWidget(ResponsiveActionBar([print_button, pdf, jpg, both], 130, 4))

        self.wizard.add_step("Zebrania", "dokument i wybór zebrania", meetings_page)
        self.wizard.add_step("Dane", "podstawowe dane wybranego zebrania", details_page)
        self.wizard.add_step("Program", "punkty programu lub wydarzenie specjalne", content_page)
        self.wizard.add_step("Podgląd", "sprawdzenie i eksport dokumentu", preview_page)

        back.clicked.connect(go_back)
        people.clicked.connect(edit_people)
        save.clicked.connect(self.save_project)
        save_as.clicked.connect(self.save_project_as)
        new_form.clicked.connect(self.new_meeting_form)
        add_normal.clicked.connect(self.add_normal)
        add_special.clicked.connect(self.add_special)
        duplicate.clicked.connect(self.duplicate_meeting)
        delete.clicked.connect(self.delete_meeting)
        up.clicked.connect(lambda: self.move_meeting(-1))
        down.clicked.connect(lambda: self.move_meeting(1))
        pdf.clicked.connect(lambda: self._export("pdf"))
        jpg.clicked.connect(lambda: self._export("jpg"))
        both.clicked.connect(lambda: self._export("both"))
        print_button.clicked.connect(lambda: print_project(self, self.renderer, self.project, "Planora"))
        self.meeting_list.currentRowChanged.connect(self.select_meeting)
        self.meeting_switch.currentIndexChanged.connect(self.select_meeting)
        previous_meeting.clicked.connect(lambda: self.switch_meeting(-1))
        next_meeting.clicked.connect(lambda: self.switch_meeting(1))
        self.meeting_list.itemDoubleClicked.connect(lambda _item: self.wizard.set_step(1))
        self.document_title.textChanged.connect(self.update_document)
        self.congregation.textChanged.connect(self.update_document)


    @staticmethod
    def _instruction(text):
        label = QLabel(text)
        label.setObjectName("helpText")
        label.setWordWrap(True)
        return label

    def _build_details_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.addWidget(self._instruction("Uzupełnij podstawowe informacje, rozpoczęcie i zakończenie zebrania."))
        identity = QGroupBox("Podstawowe informacje")
        identity_form = configure_form(QFormLayout(identity))
        self.meeting_type = QComboBox()
        self.meeting_type.addItem("Zwykłe zebranie", "normal")
        self.meeting_type.addItem("Wydarzenie specjalne", "special")
        self.meeting_date = self._date_edit()
        self.bible_reading = QLineEdit()
        self.chairman = self._person_combo()
        self.opening_prayer = self._person_combo()
        self.opening_song_time = QLineEdit()
        self.opening_song = QLineEdit()
        self.opening_comments_time = QLineEdit()
        self.opening_comments = QLineEdit()
        self.closing_comments_time = QLineEdit()
        self.closing_comments = QLineEdit()
        self.closing_song_time = QLineEdit()
        self.closing_song = QLineEdit()
        self.closing_prayer = self._person_combo()
        for label, field in [
            ("Typ:", self.meeting_type),
            ("Data:", self.meeting_date),
            ("Zakres czytania Biblii:", self.bible_reading),
            ("Przewodniczący:", self.chairman),
            ("Modlitwa początkowa:", self.opening_prayer),
        ]:
            identity_form.addRow(label, field)
        content_layout.addWidget(identity)

        opening = QGroupBox("Rozpoczęcie")
        opening_form = configure_form(QFormLayout(opening))
        for label, field in [
            ("Godzina pieśni początkowej:", self.opening_song_time),
            ("Pieśń początkowa:", self.opening_song),
            ("Godzina uwag wstępnych:", self.opening_comments_time),
            ("Uwagi wstępne:", self.opening_comments),
        ]:
            opening_form.addRow(label, field)
        content_layout.addWidget(opening)

        closing = QGroupBox("Zakończenie")
        closing_form = configure_form(QFormLayout(closing))
        for label, field in [
            ("Godzina uwag końcowych:", self.closing_comments_time),
            ("Uwagi końcowe:", self.closing_comments),
            ("Godzina pieśni końcowej:", self.closing_song_time),
            ("Pieśń końcowa:", self.closing_song),
            ("Modlitwa końcowa:", self.closing_prayer),
        ]:
            closing_form.addRow(label, field)
        content_layout.addWidget(closing)
        add_from_form = QPushButton("Dodaj jako nowe zebranie z formularza")
        add_from_form.setObjectName("primaryButton")
        add_from_form.setToolTip("Tworzy nowy termin z aktualnie widocznych danych bez dodawania pustego wpisu.")
        add_from_form.clicked.connect(self.add_from_form)
        new_form = QPushButton("Wyczyść i przygotuj nowy formularz")
        new_form.clicked.connect(self.new_meeting_form)
        content_layout.addWidget(new_form)
        content_layout.addWidget(add_from_form)
        content_layout.addStretch()
        scroll.setWidget(content)

        self.meeting_type.currentIndexChanged.connect(self.update_meeting)
        self.meeting_date.dateChanged.connect(self.update_meeting)
        for field in [
            self.bible_reading,
            self.opening_song_time,
            self.opening_song,
            self.opening_comments_time,
            self.opening_comments,
            self.closing_comments_time,
            self.closing_comments,
            self.closing_song_time,
            self.closing_song,
        ]:
            field.textChanged.connect(self.update_meeting)
        for field in (self.chairman, self.opening_prayer, self.closing_prayer):
            field.currentTextChanged.connect(self.update_meeting)
        return scroll

    def _build_program_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self._instruction(
            "Wybierz sekcję i punkt po lewej, a szczegóły uzupełnij po prawej. "
            "Zmiana zebrania jest zawsze dostępna w górnym pasku."
        ))
        self.program_context = QLabel()
        self.program_context.setObjectName("sectionTitle")
        layout.addWidget(self.program_context)
        self.program_splitter = QSplitter(Qt.Horizontal)
        navigation = QWidget()
        lists = QVBoxLayout(navigation)
        lists.setContentsMargins(0, 0, 0, 0)

        section_group = QGroupBox("Sekcje programu")
        section_side = QVBoxLayout(section_group)
        self.section_list = QListWidget()
        add_section = QPushButton("Nowa sekcja")
        add_section.setObjectName("primaryButton")
        add_standard = QPushButton("Puste sekcje")
        add_standard.setToolTip("Dodaje brakujące sekcje: Skarby, Ulepszajmy swoją służbę i Chrześcijański tryb życia.")
        add_template = QPushButton("Szablon punktów")
        add_template.setToolTip("Wstawia standardowe sekcje wraz z najczęściej używanymi punktami.")
        import_current = QPushButton("Bieżący tydzień z JW")
        import_current.setToolTip("Tworzy nowe zebranie z datą, nazwami i czasami punktów ze strony JW.")
        import_url = QPushButton("Wklej adres JW…")
        import_url.setToolTip("Tworzy nowe zebranie z programu wskazanego tygodnia JW.")
        open_jw = QPushButton("Otwórz stronę spotkań JW")
        open_jw.setToolTip("Otwiera stronę, na której można wybrać tydzień i skopiować jego adres.")
        delete_section = QPushButton("Usuń sekcję")
        delete_section.setObjectName("dangerButton")
        section_side.addWidget(self.section_list)
        section_side.addWidget(
            ResponsiveActionBar(
                [add_section, delete_section, add_standard, add_template, import_current, import_url, open_jw],
                130,
                2,
            )
        )
        lists.addWidget(section_group)

        item_group = QGroupBox("Punkty wybranej sekcji")
        item_side = QVBoxLayout(item_group)
        self.item_list = QListWidget()
        add_item = QPushButton("Dodaj punkt")
        add_item.setObjectName("primaryButton")
        duplicate_item = QPushButton("Duplikuj punkt")
        duplicate_item.setToolTip("Kopiuje wybrany punkt wraz z uczestnikami i rolami.")
        delete_item = QPushButton("Usuń punkt")
        delete_item.setObjectName("dangerButton")
        item_up = QPushButton("Wyżej")
        item_down = QPushButton("Niżej")
        item_side.addWidget(self.item_list)
        item_side.addWidget(ResponsiveActionBar([add_item, duplicate_item, delete_item, item_up, item_down], 130, 2))
        lists.addWidget(item_group)
        self.program_splitter.addWidget(navigation)

        details_scroll = QScrollArea()
        details_scroll.setWidgetResizable(True)
        details = QWidget()
        details_layout = QVBoxLayout(details)
        section_details = QGroupBox("Ustawienia wybranej sekcji")
        section_form = configure_form(QFormLayout(section_details))
        self.section_title = QLineEdit()
        self.section_color = QComboBox()
        self.section_color.addItem("Szary — Skarby ze Słowa Bożego", "#666666")
        self.section_color.addItem("Pomarańczowy — Ulepszajmy swoją służbę", "#e58b00")
        self.section_color.addItem("Czerwony — Chrześcijański tryb życia", "#c90000")
        section_form.addRow("Nazwa sekcji:", self.section_title)
        section_form.addRow("Kolor sekcji:", self.section_color)
        details_layout.addWidget(section_details)

        item_details = QGroupBox("Szczegóły wybranego punktu")
        item_form = configure_form(QFormLayout(item_details))
        self.item_time = QLineEdit()
        self.item_time.setPlaceholderText("np. 18:30")
        self.item_title = QLineEdit()
        self.item_title.setPlaceholderText("np. Rozpoczynanie rozmowy — numer doda się automatycznie")
        self.item_person_1 = self._person_combo()
        self.item_role_1 = QLineEdit()
        self.item_role_1.setPlaceholderText("Opcjonalnie, np. Prowadzący:")
        self.item_person_2 = self._person_combo()
        self.item_role_2 = QLineEdit()
        self.item_role_2.setPlaceholderText("Opcjonalnie, np. Lektor:")
        item_form.addRow("Godzina:", self.item_time)
        item_form.addRow("Nazwa punktu:", self.item_title)
        item_form.addRow("Uczestnik 1:", self.item_person_1)
        item_form.addRow("Opis roli 1:", self.item_role_1)
        item_form.addRow("Uczestnik 2:", self.item_person_2)
        item_form.addRow("Opis roli 2:", self.item_role_2)
        add_next_item = QPushButton("+ Dodaj kolejny punkt")
        add_next_item.setObjectName("primaryButton")
        item_form.addRow("", add_next_item)
        details_layout.addWidget(item_details)
        details_layout.addStretch()
        details_scroll.setWidget(details)
        self.program_splitter.addWidget(details_scroll)
        self.program_splitter.setSizes([390, 900])
        layout.addWidget(self.program_splitter, 1)

        self.section_list.currentRowChanged.connect(self.select_section)
        self.item_list.currentRowChanged.connect(self.select_item)
        add_section.clicked.connect(self.add_section)
        add_standard.clicked.connect(self.add_standard_sections)
        add_template.clicked.connect(self.apply_standard_program)
        import_current.clicked.connect(self.import_current_wol_program)
        import_url.clicked.connect(self.import_wol_program_from_url)
        open_jw.clicked.connect(self.open_jw_meetings_page)
        delete_section.clicked.connect(self.delete_section)
        add_item.clicked.connect(self.add_item)
        duplicate_item.clicked.connect(self.duplicate_item)
        add_next_item.clicked.connect(self.add_item)
        delete_item.clicked.connect(self.delete_item)
        item_up.clicked.connect(lambda: self.move_item(-1))
        item_down.clicked.connect(lambda: self.move_item(1))
        self.section_title.textChanged.connect(self.update_section)
        self.section_color.currentIndexChanged.connect(self.update_section)
        for field in (self.item_time, self.item_title, self.item_role_1, self.item_role_2):
            field.textChanged.connect(self.update_item)
        self.item_person_1.currentTextChanged.connect(self.update_item)
        self.item_person_2.currentTextChanged.connect(self.update_item)
        self.item_title.editingFinished.connect(self.refresh_item_person_filters)
        self.item_role_1.editingFinished.connect(self.refresh_item_person_filters)
        self.item_role_2.editingFinished.connect(self.refresh_item_person_filters)

        self._add_shortcut("Alt+Left", lambda: self.switch_meeting(-1))
        self._add_shortcut("Alt+Right", lambda: self.switch_meeting(1))
        self._add_shortcut("Ctrl+D", self.duplicate_meeting)
        self._add_shortcut("Ctrl+Return", self.add_item)
        return tab

    def _add_shortcut(self, sequence, callback):
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.activated.connect(callback)
        self.shortcuts.append(shortcut)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "program_splitter"):
            orientation = Qt.Vertical if self.width() < 1000 else Qt.Horizontal
            if self.program_splitter.orientation() != orientation:
                self.program_splitter.setOrientation(orientation)
                self.program_splitter.setSizes([360, 760])
        if hasattr(self, "context_label"):
            compact = self.width() < 820
            self.context_label.setVisible(not compact)
            self.meeting_position.setVisible(not compact)

    def _build_special_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self._instruction("Wydarzenie specjalne zastępuje zwykły program dużym tytułem i opcjonalnym obrazem."))
        group = QGroupBox("Szczegóły wydarzenia")
        form = configure_form(QFormLayout(group))
        self.special_title = QLineEdit()
        self.special_subtitle = QLineEdit()
        self.image_path = QLineEdit()
        choose = QPushButton("Wybierz obraz")
        image_row = QHBoxLayout()
        image_row.addWidget(self.image_path)
        image_row.addWidget(choose)
        form.addRow("Tytuł wydarzenia:", self.special_title)
        form.addRow("Podtytuł:", self.special_subtitle)
        form.addRow("Obraz:", image_row)
        layout.addWidget(group)
        layout.addStretch()
        self.special_title.textChanged.connect(self.update_special)
        self.special_subtitle.textChanged.connect(self.update_special)
        self.image_path.textChanged.connect(self.update_special)
        choose.clicked.connect(self.choose_image)
        return tab

    def _person_combo(self):
        field = configure_editable_combo(QComboBox())
        field.addItem("")
        field.addItems(self.people)
        self.person_fields.append(field)
        return field

    @staticmethod
    def _date_edit():
        field = QDateEdit()
        field.setCalendarPopup(True)
        field.setDisplayFormat("dd.MM.yyyy")
        field.setDate(QDate.currentDate())
        return field

    @staticmethod
    def _set_date(field, value):
        parsed = QDate.fromString(str(value), "yyyy-MM-dd")
        field.setDate(parsed if parsed.isValid() else QDate.currentDate())

    @staticmethod
    def _short_date(value):
        try:
            return date.fromisoformat(value).strftime("%d.%m.%Y")
        except (TypeError, ValueError):
            return "bez daty"

    def _current_meeting(self):
        meetings = self.project["meetings"]
        return meetings[self.meeting_index] if 0 <= self.meeting_index < len(meetings) else None

    def _current_section(self):
        meeting = self._current_meeting()
        sections = meeting.get("sections", []) if meeting else []
        return sections[self.section_index] if 0 <= self.section_index < len(sections) else None

    def _current_item(self):
        section_value = self._current_section()
        items = section_value.get("items", []) if section_value else []
        return items[self.item_index] if 0 <= self.item_index < len(items) else None

    def update_document(self, *_args):
        self.project["document_title"] = self.document_title.text()
        self.project["congregation"] = self.congregation.text()
        self.refresh_preview()

    def refresh_meetings(self, selected=None):
        self.meeting_list.blockSignals(True)
        self.meeting_switch.blockSignals(True)
        self.meeting_list.clear()
        self.meeting_switch.clear()
        for meeting in self.project["meetings"]:
            if meeting.get("type") == "special":
                detail = meeting.get("special_title") or "wydarzenie specjalne"
            else:
                detail = meeting.get("bible_reading") or "zwykłe zebranie"
            self.meeting_list.addItem(f"{self._short_date(meeting.get('date', ''))}\n{detail}")
            self.meeting_switch.addItem(f"{self._short_date(meeting.get('date', ''))} · {detail}")
        if selected is not None:
            self.meeting_list.setCurrentRow(selected)
            self.meeting_switch.setCurrentIndex(selected)
        self.meeting_list.blockSignals(False)
        self.meeting_switch.blockSignals(False)
        count = len(self.project["meetings"])
        if count and selected is not None and 0 <= selected < count:
            self.meeting_position.setText(f"Zebranie {selected + 1} z {count}")
        elif not count:
            self.meeting_position.setText("Brak zebrań")

    def select_meeting(self, index):
        meetings = self.project["meetings"]
        if not 0 <= index < len(meetings):
            return
        self.meeting_index = index
        meeting = meetings[index]
        self.meeting_list.blockSignals(True)
        self.meeting_switch.blockSignals(True)
        self.meeting_list.setCurrentRow(index)
        self.meeting_switch.setCurrentIndex(index)
        self.meeting_list.blockSignals(False)
        self.meeting_switch.blockSignals(False)
        self.meeting_position.setText(f"Zebranie {index + 1} z {len(meetings)}")
        fields = [
            self.meeting_type, self.meeting_date, self.bible_reading, self.chairman, self.opening_prayer,
            self.opening_song_time, self.opening_song, self.opening_comments_time, self.opening_comments,
            self.closing_comments_time, self.closing_comments, self.closing_song_time, self.closing_song,
            self.closing_prayer, self.special_title, self.special_subtitle, self.image_path,
        ]
        for field in fields:
            field.blockSignals(True)
        self.meeting_type.setCurrentIndex(1 if meeting.get("type") == "special" else 0)
        self._set_date(self.meeting_date, meeting.get("date", ""))
        for field, key in [
            (self.bible_reading, "bible_reading"), (self.opening_song_time, "opening_song_time"),
            (self.opening_song, "opening_song"), (self.opening_comments_time, "opening_comments_time"),
            (self.opening_comments, "opening_comments"), (self.closing_comments_time, "closing_comments_time"),
            (self.closing_comments, "closing_comments"), (self.closing_song_time, "closing_song_time"),
            (self.closing_song, "closing_song"), (self.special_title, "special_title"),
            (self.special_subtitle, "special_subtitle"), (self.image_path, "image_path"),
        ]:
            field.setText(meeting.get(key, ""))
        self.chairman.setCurrentText(meeting.get("chairman", ""))
        self.opening_prayer.setCurrentText(meeting.get("opening_prayer", ""))
        self.closing_prayer.setCurrentText(meeting.get("closing_prayer", ""))
        for field in fields:
            field.blockSignals(False)
        is_special = meeting.get("type") == "special"
        self.content_stack.setCurrentWidget(self.special_widget if is_special else self.program_widget)
        self.refresh_sections(0)
        self.select_section(0)
        self.refresh_program_context()

    def switch_meeting(self, delta):
        target = self.meeting_index + delta
        if 0 <= target < len(self.project["meetings"]):
            self.select_meeting(target)

    def refresh_program_context(self):
        meeting = self._current_meeting()
        if not hasattr(self, "program_context"):
            return
        if not meeting:
            self.program_context.setText("Najpierw dodaj zebranie.")
            return
        section_value = self._current_section()
        section_text = section_value.get("title", "") if section_value else "bez wybranej sekcji"
        self.program_context.setText(
            f"Zebranie: {self._short_date(meeting.get('date', ''))}  •  Sekcja: {section_text}"
        )

    def update_meeting(self, *_args):
        meeting = self._current_meeting()
        new_type = self.meeting_type.currentData()
        self.content_stack.setCurrentWidget(self.special_widget if new_type == "special" else self.program_widget)
        if not meeting:
            return
        meeting["type"] = new_type
        meeting["date"] = self.meeting_date.date().toString("yyyy-MM-dd")
        for field, key in [
            (self.bible_reading, "bible_reading"), (self.opening_song_time, "opening_song_time"),
            (self.opening_song, "opening_song"), (self.opening_comments_time, "opening_comments_time"),
            (self.opening_comments, "opening_comments"), (self.closing_comments_time, "closing_comments_time"),
            (self.closing_comments, "closing_comments"), (self.closing_song_time, "closing_song_time"),
            (self.closing_song, "closing_song"),
        ]:
            meeting[key] = field.text()
        meeting["chairman"] = self.chairman.currentText()
        meeting["opening_prayer"] = self.opening_prayer.currentText()
        meeting["closing_prayer"] = self.closing_prayer.currentText()
        if new_type == "normal":
            meeting.setdefault("sections", [])
        self.refresh_meetings(self.meeting_index)
        self.refresh_program_context()
        self.refresh_preview()

    def update_special(self, *_args):
        meeting = self._current_meeting()
        if not meeting:
            return
        meeting["special_title"] = self.special_title.text()
        meeting["special_subtitle"] = self.special_subtitle.text()
        meeting["image_path"] = self.image_path.text()
        self.refresh_preview()

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Wybierz obraz", str(USER_DATA_DIR), "Obrazy (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.image_path.setText(path)

    def refresh_sections(self, selected=None):
        meeting = self._current_meeting()
        self.section_list.blockSignals(True)
        self.section_list.clear()
        for section_value in meeting.get("sections", []) if meeting else []:
            self.section_list.addItem(section_value.get("title", "sekcja"))
        if selected is not None:
            self.section_list.setCurrentRow(selected)
        self.section_list.blockSignals(False)

    def select_section(self, index):
        meeting = self._current_meeting()
        sections = meeting.get("sections", []) if meeting else []
        if not 0 <= index < len(sections):
            self.section_index = -1
            self.refresh_items()
            return
        self.section_index = index
        value = sections[index]
        for field in (self.section_title, self.section_color):
            field.blockSignals(True)
        self.section_title.setText(value.get("title", ""))
        color_index = self.section_color.findData(value.get("color", "#666666"))
        self.section_color.setCurrentIndex(max(0, color_index))
        for field in (self.section_title, self.section_color):
            field.blockSignals(False)
        self.refresh_items(0)
        self.select_item(0)
        self.refresh_program_context()

    def update_section(self, *_args):
        value = self._current_section()
        if not value:
            return
        value["title"] = self.section_title.text()
        value["color"] = self.section_color.currentData()
        self.refresh_sections(self.section_index)
        self.refresh_program_context()
        self.refresh_item_person_filters()
        self.refresh_preview()

    def refresh_items(self, selected=None):
        value = self._current_section()
        self.item_list.blockSignals(True)
        self.item_list.clear()
        for index, item in enumerate(value.get("items", []) if value else []):
            number = self._program_item_number(self.section_index, index)
            title = numbered_program_title(number, item.get("title", ""))
            self.item_list.addItem(f"{item.get('time', '')}  {title}".strip())
        if selected is not None:
            self.item_list.setCurrentRow(selected)
        self.item_list.blockSignals(False)

    def _program_item_number(self, section_index, item_index):
        meeting = self._current_meeting()
        sections = meeting.get("sections", []) if meeting else []
        return 1 + item_index + sum(len(value.get("items", [])) for value in sections[:section_index])

    def select_item(self, index):
        value = self._current_section()
        items = value.get("items", []) if value else []
        if not 0 <= index < len(items):
            self.item_index = -1
            return
        self.item_index = index
        item = items[index]
        fields = [self.item_time, self.item_title, self.item_person_1, self.item_role_1, self.item_person_2, self.item_role_2]
        for field in fields:
            field.blockSignals(True)
        self.item_time.setText(item.get("time", ""))
        self.item_title.setText(item.get("title", ""))
        self.item_role_1.setText(item.get("role_1", ""))
        self.item_role_2.setText(item.get("role_2", ""))
        self._populate_item_person_fields(
            item.get("participant_1", ""),
            item.get("participant_2", ""),
        )
        for field in fields:
            field.blockSignals(False)

    def update_item(self, *_args):
        item = self._current_item()
        if not item:
            return
        item.update(
            {
                "time": self.item_time.text(),
                "title": self.item_title.text(),
                "participant_1": self.item_person_1.currentText(),
                "role_1": self.item_role_1.text(),
                "participant_2": self.item_person_2.currentText(),
                "role_2": self.item_role_2.text(),
            }
        )
        self.refresh_items(self.item_index)
        self.refresh_preview()

    def add_normal(self):
        self.project["meetings"].append(self._meeting_from_form("normal"))
        self._select_last_meeting()
        self.wizard.set_step(1)

    def add_special(self):
        self.project["meetings"].append(self._meeting_from_form("special"))
        self._select_last_meeting()
        self.wizard.set_step(1)

    def add_from_form(self):
        self.project["meetings"].append(self._meeting_from_form(self.meeting_type.currentData()))
        self._select_last_meeting()
        self.wizard.set_step(1)

    def new_meeting_form(self):
        self.meeting_index = -1
        self.section_index = -1
        self.item_index = -1
        self.meeting_list.blockSignals(True)
        self.meeting_switch.blockSignals(True)
        self.meeting_list.setCurrentRow(-1)
        self.meeting_list.clearSelection()
        self.meeting_switch.setCurrentIndex(-1)
        self.meeting_list.blockSignals(False)
        self.meeting_switch.blockSignals(False)
        fields = [
            self.meeting_type,
            self.meeting_date,
            self.bible_reading,
            self.chairman,
            self.opening_prayer,
            self.opening_song_time,
            self.opening_song,
            self.opening_comments_time,
            self.opening_comments,
            self.closing_comments_time,
            self.closing_comments,
            self.closing_song_time,
            self.closing_song,
            self.closing_prayer,
            self.special_title,
            self.special_subtitle,
            self.image_path,
        ]
        for field in fields:
            field.blockSignals(True)
        self.meeting_type.setCurrentIndex(0)
        self.meeting_date.setDate(QDate.currentDate())
        for field in (
            self.bible_reading,
            self.opening_song_time,
            self.opening_song,
            self.opening_comments_time,
            self.opening_comments,
            self.closing_comments_time,
            self.closing_comments,
            self.closing_song_time,
            self.closing_song,
            self.special_title,
            self.special_subtitle,
            self.image_path,
        ):
            field.clear()
        for field in (self.chairman, self.opening_prayer, self.closing_prayer):
            field.setCurrentText("")
        for field in fields:
            field.blockSignals(False)
        self.content_stack.setCurrentWidget(self.program_widget)
        self.refresh_sections()
        self.refresh_items()
        self.meeting_position.setText("Nowy formularz")
        self.refresh_program_context()
        self.wizard.set_step(1)
        self.meeting_date.setFocus()

    def _meeting_from_form(self, meeting_type):
        duty_date = self.meeting_date.date().toString("yyyy-MM-dd")
        if meeting_type == "special":
            meeting = special_event(duty_date)
            meeting.update(
                {
                    "special_title": self.special_title.text(),
                    "special_subtitle": self.special_subtitle.text(),
                    "image_path": self.image_path.text(),
                }
            )
            return meeting
        meeting = normal_meeting(duty_date)
        meeting.update(
            {
                "bible_reading": self.bible_reading.text(),
                "chairman": self.chairman.currentText(),
                "opening_prayer": self.opening_prayer.currentText(),
                "opening_song_time": self.opening_song_time.text(),
                "opening_song": self.opening_song.text(),
                "opening_comments_time": self.opening_comments_time.text(),
                "opening_comments": self.opening_comments.text(),
                "closing_comments_time": self.closing_comments_time.text(),
                "closing_comments": self.closing_comments.text(),
                "closing_song_time": self.closing_song_time.text(),
                "closing_song": self.closing_song.text(),
                "closing_prayer": self.closing_prayer.currentText(),
            }
        )
        return meeting

    def duplicate_meeting(self):
        meeting = self._current_meeting()
        if not meeting:
            return
        duplicate = copy.deepcopy(meeting)
        current_date = QDate.fromString(str(duplicate.get("date", "")), "yyyy-MM-dd")
        if current_date.isValid():
            duplicate["date"] = current_date.addDays(7).toString("yyyy-MM-dd")
        target = self.meeting_index + 1
        self.project["meetings"].insert(target, duplicate)
        self.refresh_meetings(target)
        self.select_meeting(target)
        self.refresh_preview()

    def _select_last_meeting(self):
        self.meeting_index = len(self.project["meetings"]) - 1
        self.refresh_meetings(self.meeting_index)
        self.select_meeting(self.meeting_index)
        self.refresh_preview()

    def delete_meeting(self):
        meetings = self.project["meetings"]
        if 0 <= self.meeting_index < len(meetings):
            meetings.pop(self.meeting_index)
            self.meeting_index = min(self.meeting_index, len(meetings) - 1)
            self.refresh_meetings(self.meeting_index)
            self.select_meeting(self.meeting_index)
            self.refresh_preview()

    def move_meeting(self, delta):
        meetings = self.project["meetings"]
        target = self.meeting_index + delta
        if 0 <= self.meeting_index < len(meetings) and 0 <= target < len(meetings):
            meetings[self.meeting_index], meetings[target] = meetings[target], meetings[self.meeting_index]
            self.meeting_index = target
            self.refresh_meetings(target)
            self.select_meeting(target)
            self.refresh_preview()

    def add_section(self):
        meeting = self._current_meeting()
        if not meeting:
            return
        meeting.setdefault("sections", []).append(section("NOWA SEKCJA", "#666666"))
        self.section_index = len(meeting["sections"]) - 1
        self.refresh_sections(self.section_index)
        self.select_section(self.section_index)
        self.section_title.setFocus()
        self.section_title.selectAll()
        self.refresh_preview()

    def add_standard_sections(self):
        meeting = self._current_meeting()
        if not meeting or meeting.get("type") == "special":
            return
        sections = meeting.setdefault("sections", [])
        presets = [
            ("SKARBY ZE SŁOWA BOŻEGO", "#666666"),
            ("ULEPSZAJMY SWOJĄ SŁUŻBĘ", "#e58b00"),
            ("CHRZEŚCIJAŃSKI TRYB ŻYCIA", "#c90000"),
        ]
        known = {value.get("title", "").casefold() for value in sections}
        for title, color in presets:
            if title.casefold() not in known:
                sections.append(section(title, color))
        self.section_index = 0 if sections else -1
        self.refresh_sections(self.section_index)
        self.select_section(self.section_index)
        self.refresh_preview()

    def apply_standard_program(self):
        self._replace_program_sections(standard_program_sections(), "")

    def import_current_wol_program(self):
        self._import_wol_program(current_week_url())

    def import_wol_program_from_url(self):
        url, accepted = QInputDialog.getText(
            self,
            "Import programu z JW",
            "Wklej pełny adres wybranego tygodnia ze strony JW:",
            text=current_week_url(),
        )
        if accepted and url.strip():
            self._import_wol_program(url.strip())

    @staticmethod
    def open_jw_meetings_page():
        QDesktopServices.openUrl(QUrl(JW_MEETINGS_BASE_URL))

    def _import_wol_program(self, url):
        try:
            imported = fetch_wol_program(url)
        except WolImportError as exc:
            QMessageBox.warning(
                self,
                "Nie udało się pobrać programu",
                f"{exc}\n\nMożesz nadal użyć lokalnego przycisku „Wstaw szablon punktów”.",
            )
            return
        append_imported_meeting(self.project, copy.deepcopy(imported))
        self._select_last_meeting()
        self.wizard.set_step(2)
        QMessageBox.information(
            self,
            "Program pobrany",
            f"Dodano nowe zebranie z datą {imported['meeting_date']}. "
            "Pobrano nazwy punktów i czasy trwania; przydziały osób pozostały puste.",
        )

    def _replace_program_sections(self, sections, bible_reading):
        meeting = self._current_meeting()
        if not meeting or meeting.get("type") == "special":
            QMessageBox.information(self, "Program", "Najpierw wybierz zwykłe zebranie.")
            return False
        if meeting.get("sections"):
            answer = QMessageBox.question(
                self,
                "Zastąpić program?",
                "Wybrane zebranie ma już punkty programu. Czy zastąpić je nowym szablonem?",
            )
            if answer != QMessageBox.Yes:
                return False
        meeting["sections"] = copy.deepcopy(sections)
        if bible_reading:
            meeting["bible_reading"] = bible_reading
            self.bible_reading.setText(bible_reading)
        self.section_index = 0 if meeting["sections"] else -1
        self.item_index = 0
        self.refresh_sections(self.section_index)
        self.select_section(self.section_index)
        self.refresh_preview()
        return True

    def delete_section(self):
        meeting = self._current_meeting()
        sections = meeting.get("sections", []) if meeting else []
        if 0 <= self.section_index < len(sections):
            sections.pop(self.section_index)
            self.section_index = min(self.section_index, len(sections) - 1)
            self.refresh_sections(self.section_index)
            self.select_section(self.section_index)
            self.refresh_preview()

    def add_item(self):
        value = self._current_section()
        if not value:
            return
        value.setdefault("items", []).append(program_item("", "Nowy punkt"))
        self.item_index = len(value["items"]) - 1
        self.refresh_items(self.item_index)
        self.select_item(self.item_index)
        self.item_title.setFocus()
        self.item_title.selectAll()
        self.refresh_preview()

    def delete_item(self):
        value = self._current_section()
        items = value.get("items", []) if value else []
        if 0 <= self.item_index < len(items):
            items.pop(self.item_index)
            self.item_index = min(self.item_index, len(items) - 1)
            self.refresh_items(self.item_index)
            self.select_item(self.item_index)
            self.refresh_preview()

    def duplicate_item(self):
        value = self._current_section()
        item = self._current_item()
        if value is None or item is None:
            return
        target = self.item_index + 1
        value.setdefault("items", []).insert(target, copy.deepcopy(item))
        self.item_index = target
        self.refresh_items(target)
        self.select_item(target)
        self.item_time.setFocus()
        self.item_time.selectAll()
        self.refresh_preview()

    def move_item(self, delta):
        value = self._current_section()
        items = value.get("items", []) if value else []
        target = self.item_index + delta
        if 0 <= self.item_index < len(items) and 0 <= target < len(items):
            items[self.item_index], items[target] = items[target], items[self.item_index]
            self.item_index = target
            self.refresh_items(target)
            self.select_item(target)
            self.refresh_preview()

    def refresh_preview(self):
        try:
            pages = self.renderer.render_pages(self.project)
            image = pages[0].copy()
            self.preview.set_image(image, len(pages))
        except Exception as exc:
            self.preview.set_error(str(exc))

    def set_people(self, people):
        self.people = list(people)
        for field in self.person_fields:
            current = field.currentText()
            field.blockSignals(True)
            field.clear()
            field.addItem("")
            field.addItems(self.people)
            field.setCurrentText(current)
            field.blockSignals(False)

    def set_role_people(self, role_people: dict[str, list[str]]):
        self.role_people = {role: list(people) for role, people in role_people.items()}
        self.refresh_item_person_filters()

    @staticmethod
    def _item_required_role(title: str, role_text: str, section_title: str = "") -> str:
        source = f"{role_text} {title}".casefold()
        section_source = str(section_title).casefold()
        if "modlitw" in source:
            return "prayer"
        if "czytanie biblii" in source or "ulepszajmy" in section_source:
            return "training_part"
        if "lektor" in source:
            return "reader"
        if "przewodnicz" in source:
            return "chairman"
        return "midweek_other"

    def _populate_item_person_fields(self, participant_1="", participant_2=""):
        title = self.item_title.text()
        section_value = self._current_section() or {}
        section_title = section_value.get("title", "")
        roles = (
            self._item_required_role(title, self.item_role_1.text(), section_title),
            self._item_required_role(title, self.item_role_2.text(), section_title),
        )
        for field, role, current in zip(
            (self.item_person_1, self.item_person_2),
            roles,
            (participant_1, participant_2),
        ):
            field.clear()
            field.setEditable(True)
            field.addItem("")
            field.addItems(self.role_people.get(role, self.people))
            field.setCurrentText(current)
            field.setToolTip(
                f"Lista podpowiada osoby pasujące do przydziału: {ASSIGNMENT_OPTIONS[role]}. "
                "Możesz też wpisać inną osobę ręcznie."
            )

    def refresh_item_person_filters(self):
        fields = (self.item_person_1, self.item_person_2)
        current = tuple(field.currentText() for field in fields)
        for field in fields:
            field.blockSignals(True)
        self._populate_item_person_fields(*current)
        for field in fields:
            field.blockSignals(False)
        self.update_item()

    def save_project(self):
        if self.project_path is None:
            return self.save_project_as()
        try:
            ProjectIO.save_project(self.project_path, self.project)
            QMessageBox.information(self, "Zapisano", f"Projekt zapisany:\n{self.project_path}")
        except OSError as exc:
            QMessageBox.warning(self, "Błąd zapisu", str(exc))

    def save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Zapisz projekt", str(PROJECTS_DIR / "zebrania-w-tygodniu.json"), "Projekt JSON (*.json)"
        )
        if path:
            self.project_path = Path(path)
            self.save_project()

    def _export(self, kind):
        if not confirm_export(self, self.project):
            return
        default_name = "Zebrania-w-tygodniu.jpg" if kind == "jpg" else "Zebrania-w-tygodniu.pdf"
        file_filter = "JPG (*.jpg)" if kind == "jpg" else "PDF (*.pdf)"
        path, _ = QFileDialog.getSaveFileName(self, "Eksport grafiku", default_name, file_filter)
        if not path:
            return
        try:
            if kind in ("pdf", "both"):
                self.renderer.export_pdf(path, self.project)
            if kind in ("jpg", "both"):
                jpg_path = path if kind == "jpg" else str(Path(path).with_suffix(".jpg"))
                self.renderer.export_jpg(jpg_path, self.project)
            QMessageBox.information(self, "Gotowe", "Grafik został wyeksportowany.")
        except Exception as exc:
            QMessageBox.warning(self, "Błąd eksportu", str(exc))
