import json
import io
import subprocess
import tempfile
import unittest
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.config import UPDATE_URL
from app.core.assignment_tools import (
    assigned_people_by_date,
    archive_assignments,
    assignment_rows_for_person,
    build_service_meetings_plan,
    extract_assignments,
    export_ics,
    export_person_assignments,
    generate_recurring_dates,
    person_assignments,
    shift_project_dates,
)
from app.core.people_roles import ALL_ROLES, eligible_people, normalize_profiles
from app.core.group_tools import group_leaders_from_project, latest_group_leaders, normalize_group_name
from app.core.project_io import DEFAULT_PEOPLE, ProjectIO
from app.core.project_archive import ARCHIVE_ID_KEY, ProjectArchive
from app.core.project_history import ProjectHistory
from app.core.project_validation import validate_project
from app.core.template_registry import TemplateRegistry
from app.core.updater import UpdateChecker, UpdateCheckError
from app.core.update_installer import (
    apply_update,
    _independent_process_environment,
    _launch_installed_app,
    _replace_installation,
    consume_update_result,
    run_update_installer_from_args,
    validate_update_archive,
)
from app.templates.cleaning_attendants.conflicts import find_conflicts
from app.templates.cleaning_attendants.default_project import attendant_row, weekly_row
from app.templates.field_service_groups.default_project import ROLE_MEMBER, group, member
from app.templates.field_service_groups.default_project import ROLE_LEADER
from app.templates.midweek_meeting.default_project import normal_meeting, program_item, section
from app.templates.midweek_meeting.renderer import numbered_program_title
from app.templates.service_meetings.default_project import meeting_row
from app.gui.theme_manager import THEMES, build_stylesheet
from app.gui.ui_feedback import UiFeedback
from tools.update_download_catalog import update_catalog
from tools.generate_windows_version_info import render_version_info, version_tuple


class UpdateCheckerTests(unittest.TestCase):
    def test_official_update_url_points_to_planora_repository(self):
        self.assertEqual(
            UPDATE_URL,
            "https://raw.githubusercontent.com/KamilMordarski/planora/main/update.json",
        )

    def test_compare_versions(self):
        checker = UpdateChecker(current_version="1.2.3")

        self.assertEqual(checker.compare_versions("1.2.4"), 1)
        self.assertEqual(checker.compare_versions("1.2.3"), 0)
        self.assertEqual(checker.compare_versions("1.2"), -1)

    def test_online_payload_is_compared_and_stored(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            @staticmethod
            def read():
                return b'{"latest_version":"2.0.0","download_url":"https://example.com"}'

        checker = UpdateChecker("https://example.com/update.json", current_version="1.5.0")
        with patch("app.core.updater.urlopen", return_value=Response()):
            self.assertTrue(checker.check_for_updates())
        self.assertEqual(checker.get_update_info()["latest_version"], "2.0.0")

    def test_missing_update_url_has_clear_error(self):
        with self.assertRaises(UpdateCheckError):
            UpdateChecker("").check_for_updates()

    def test_platform_download_url_and_filename_are_selected(self):
        checker = UpdateChecker()
        checker._update_info = {
            "download_url": "https://example.com/fallback.zip",
            "download_urls": {
                "windows": "https://example.com/Planora-Windows.zip",
                "macos": "https://example.com/Planora-macOS.zip",
            },
        }

        self.assertEqual(checker.get_download_url("windows"), "https://example.com/Planora-Windows.zip")
        self.assertEqual(checker.suggested_filename("macos"), "Planora-macOS.zip")

    def test_update_is_downloaded_directly_to_selected_file(self):
        payload = b"planora-update"

        class Response:
            headers = {"Content-Length": str(len(payload))}

            def __init__(self):
                self.stream = io.BytesIO(payload)

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, size=-1):
                return self.stream.read(size)

        checker = UpdateChecker()
        checker._update_info = {"download_url": "https://example.com/Planora-Windows.zip"}
        progress = []
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "Planora-Windows.zip"
            with patch("app.core.updater.urlopen", return_value=Response()):
                downloaded = checker.download_update(
                    destination,
                    lambda current, total: progress.append((current, total)) or True,
                )

            self.assertEqual(downloaded.read_bytes(), payload)
            self.assertEqual(progress[-1], (len(payload), len(payload)))


class UpdateInstallerTests(unittest.TestCase):
    def test_restart_environment_resets_pyinstaller_state(self):
        with patch.dict(
            "app.core.update_installer.os.environ",
            {"_PYI_PARENT_PROCESS_LEVEL": "2"},
            clear=True,
        ):
            environment = _independent_process_environment()

        self.assertEqual(environment["PYINSTALLER_RESET_ENVIRONMENT"], "1")

    def test_windows_restart_runs_as_independent_process(self):
        target = Path("C:/Planora/Planora.exe")
        process = MagicMock()
        process.wait.side_effect = subprocess.TimeoutExpired(cmd=str(target), timeout=2.0)

        with (
            patch("app.core.update_installer.sys.platform", "win32"),
            patch("app.core.update_installer.subprocess.CREATE_NEW_PROCESS_GROUP", 0x200, create=True),
            patch("app.core.update_installer.subprocess.DETACHED_PROCESS", 0x8, create=True),
            patch("app.core.update_installer.subprocess.Popen", return_value=process) as popen,
        ):
            _launch_installed_app(target)

        kwargs = popen.call_args.kwargs
        self.assertEqual(kwargs["cwd"], str(target.parent))
        self.assertEqual(kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")
        process.wait.assert_called_once_with(timeout=2.0)

    def test_windows_restart_rejects_application_that_exits_immediately(self):
        target = Path("C:/Planora/Planora.exe")
        process = MagicMock()
        process.wait.return_value = 1

        with (
            patch("app.core.update_installer.sys.platform", "win32"),
            patch("app.core.update_installer.subprocess.CREATE_NEW_PROCESS_GROUP", 0x200, create=True),
            patch("app.core.update_installer.subprocess.DETACHED_PROCESS", 0x8, create=True),
            patch("app.core.update_installer.subprocess.Popen", return_value=process),
            self.assertRaisesRegex(OSError, "kod 1"),
        ):
            _launch_installed_app(target)

    def test_windows_update_archive_contains_expected_application(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "Planora-Windows.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("Planora.exe", b"new-version")

            validate_update_archive(archive, "windows")

    def test_macos_update_archive_contains_expected_application(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "Planora-macOS.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("Planora.app/Contents/MacOS/Planora", b"new-version")

            validate_update_archive(archive, "macos")

    def test_installation_file_is_replaced_and_backup_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "Planora.exe"
            payload = root / "new" / "Planora.exe"
            payload.parent.mkdir()
            target.write_bytes(b"old-version")
            payload.write_bytes(b"new-version")

            _replace_installation(payload, target)

            self.assertEqual(target.read_bytes(), b"new-version")
            self.assertFalse((root / "Planora.exe.previous").exists())

    def test_installation_backup_can_be_kept_until_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "Planora.exe"
            payload = root / "new" / "Planora.exe"
            payload.parent.mkdir()
            target.write_bytes(b"old-version")
            payload.write_bytes(b"new-version")

            backup = _replace_installation(payload, target, keep_backup=True)

            self.assertEqual(target.read_bytes(), b"new-version")
            self.assertEqual(backup.read_bytes(), b"old-version")

    def test_complete_windows_update_cycle_replaces_application(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "Planora-Windows.zip"
            target = root / "installed" / "Planora.exe"
            target.parent.mkdir()
            target.write_bytes(b"old-version")
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("Planora.exe", b"new-version")

            with patch("app.core.update_installer._wait_for_process_exit"):
                apply_update(archive, target, parent_pid=123, platform="windows")

            self.assertEqual(target.read_bytes(), b"new-version")

    def test_update_result_is_consumed_once(self):
        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory) / "result.json"
            result_path.write_text('{"success": true, "message": "ok"}', encoding="utf-8")

            self.assertEqual(consume_update_result(result_path)["message"], "ok")
            self.assertIsNone(consume_update_result(result_path))

    def test_failed_restart_restores_previous_application(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "update.zip"
            target = root / "Planora.exe"
            backup = root / "Planora.exe.previous"
            result = root / "result.json"
            target.write_bytes(b"new-version")
            backup.write_bytes(b"old-version")
            arguments = [
                "--apply-update",
                str(archive),
                "--target",
                str(target),
                "--parent-pid",
                "123",
                "--result-file",
                str(result),
                "--version",
                "test",
            ]

            with (
                patch("app.core.update_installer.apply_update", return_value=backup),
                patch("app.core.update_installer._launch_installed_app", side_effect=[OSError("start failed"), None]),
            ):
                exit_code = run_update_installer_from_args(arguments)

            self.assertEqual(exit_code, 1)
            self.assertEqual(target.read_bytes(), b"old-version")
            self.assertFalse(json.loads(result.read_text(encoding="utf-8"))["success"])


class DownloadCatalogTests(unittest.TestCase):
    def test_catalog_contains_latest_and_versioned_executable_links(self):
        with tempfile.TemporaryDirectory() as directory:
            downloads = Path(directory) / "downloads"
            update_catalog("KamilMordarski/planora", "v1.7.3", downloads)
            update_catalog("KamilMordarski/planora", "1.8.0", downloads)

            latest = (downloads / "latest" / "README.md").read_text(encoding="utf-8")
            version = (downloads / "1.7.3" / "README.md").read_text(encoding="utf-8")
            root = (downloads / "README.md").read_text(encoding="utf-8")

            self.assertIn("Planora-latest.exe", latest)
            self.assertIn("SHA256SUMS.txt", latest)
            self.assertIn("Planora-1.7.3.exe", version)
            self.assertLess(root.index("[1.8.0]"), root.index("[1.7.3]"))


class WindowsVersionInfoTests(unittest.TestCase):
    def test_version_info_contains_product_identity_and_numeric_version(self):
        version_info = render_version_info("1.7.3")

        self.assertEqual(version_tuple("1.7.3"), (1, 7, 3, 0))
        self.assertIn("ProductName', 'Planora", version_info)
        self.assertIn("CompanyName', 'Kamil Mordarski", version_info)
        self.assertIn("filevers=(1, 7, 3, 0)", version_info)


class ThemeTests(unittest.TestCase):
    def test_multiple_themes_and_custom_accent_are_available(self):
        self.assertGreaterEqual(len(THEMES), 5)
        stylesheet = build_stylesheet({"theme": "graphite", "accent_color": "#123456", "font_scale": 120})
        self.assertIn("#123456", stylesheet)
        self.assertIn("QPushButton", stylesheet)

    def test_density_and_corner_settings_change_stylesheet(self):
        stylesheet = build_stylesheet(
            {
                "theme": "ocean",
                "font_scale": 100,
                "interface_density": "compact",
                "corner_style": "square",
            }
        )
        self.assertIn("border-radius: 2px", stylesheet)
        self.assertIn("QComboBox QLineEdit", stylesheet)


class UiFeedbackTests(unittest.TestCase):
    def test_all_feedback_sounds_can_be_generated(self):
        names = ("click", "hover", "navigate", "switch", "add", "remove", "open", "save", "export", "confirm")
        with tempfile.TemporaryDirectory() as directory:
            for name in names:
                path = Path(directory) / f"{name}.wav"
                UiFeedback._write_sound(path, name)
                self.assertGreater(path.stat().st_size, 500)


class TemplateRegistryTests(unittest.TestCase):
    def test_new_projects_start_without_schedule_entries(self):
        self.assertEqual(TemplateRegistry.get("public_talk_watchtower").default_project["weeks"], [])
        self.assertEqual(TemplateRegistry.get("cleaning_attendants").default_project["weekly_assignments"], [])
        self.assertEqual(TemplateRegistry.get("cleaning_attendants").default_project["attendant_assignments"], [])
        self.assertEqual(TemplateRegistry.get("midweek_meeting").default_project["meetings"], [])
        self.assertEqual(TemplateRegistry.get("service_meetings").default_project["meetings"], [])
        groups = TemplateRegistry.get("field_service_groups").default_project["groups"]
        self.assertEqual(len(groups), 5)
        self.assertTrue(all(value["members"] == [] for value in groups))
        self.assertEqual(TemplateRegistry.get("field_service_groups").default_project["congregation"], "")

    def test_public_talk_template_is_registered(self):
        template = TemplateRegistry.get("public_talk_watchtower")

        self.assertIsNotNone(template)
        self.assertEqual(template.default_project["template_id"], template.id)
        self.assertTrue(callable(template.editor_class))
        self.assertTrue(callable(template.renderer_class))

    def test_cleaning_attendants_template_is_registered(self):
        template = TemplateRegistry.get("cleaning_attendants")

        self.assertIsNotNone(template)
        self.assertEqual(template.default_project["template_id"], template.id)

    def test_midweek_meeting_template_is_registered_and_renders(self):
        template = TemplateRegistry.get("midweek_meeting")

        self.assertIsNotNone(template)
        self.assertEqual(template.default_project["template_id"], template.id)
        self.assertEqual(len(template.renderer_class.render_pages(template.default_project)), 1)

    def test_midweek_program_titles_are_numbered_without_duplicate_manual_prefix(self):
        self.assertEqual(numbered_program_title(1, "Rozpoczynanie rozmowy"), "1. Rozpoczynanie rozmowy")
        self.assertEqual(numbered_program_title(2, "7. Nie daj się zwieść"), "2. Nie daj się zwieść")

    def test_midweek_numbering_starts_after_opening_comments_and_crosses_sections(self):
        template = TemplateRegistry.get("midweek_meeting")
        project = template.default_project
        meeting = normal_meeting("2026-06-17")
        meeting["opening_song"] = "Pieśń początkowa"
        meeting["opening_comments"] = "Uwagi wstępne"
        meeting["sections"] = [
            section("Sekcja 1", "#666666", [program_item("18:06", "Pierwszy punkt")]),
            section("Sekcja 2", "#e58b00", [program_item("18:16", "Drugi punkt")]),
        ]
        meeting["closing_comments"] = "Uwagi końcowe"
        project["meetings"] = [meeting]
        titles = []

        def capture(_draw, y, _time, title, *_args):
            titles.append(title)
            return y + 68

        with patch.object(template.renderer_class, "_draw_standard_line", side_effect=capture):
            template.renderer_class.render_pages(project)

        self.assertEqual(
            titles,
            ["Pieśń początkowa", "Uwagi wstępne", "1. Pierwszy punkt", "2. Drugi punkt", "Uwagi końcowe", ""],
        )

    def test_field_service_groups_template_is_registered_and_roles_default_to_member(self):
        template = TemplateRegistry.get("field_service_groups")

        self.assertIsNotNone(template)
        self.assertEqual(template.default_project["template_id"], template.id)
        self.assertEqual(member("Jan Test")["role"], ROLE_MEMBER)

    def test_service_meetings_template_is_registered_and_fully_editable(self):
        template = TemplateRegistry.get("service_meetings")
        project = template.default_project
        project["title"] = "Własny tytuł"
        project["headers"]["place"] = "DOWOLNA KOLUMNA"
        project["colors"]["header_fill"] = "#123456"
        project["meetings"] = [meeting_row("Dowolna data", "18:00", "Dowolne miejsce", "Jan Test", "#abcdef")]

        pages = template.renderer_class.render_pages(project)

        self.assertIsNotNone(template)
        self.assertEqual(project["meetings"][0]["date"], "Dowolna data")
        self.assertEqual(len(pages), 1)

    def test_service_meetings_renderer_paginates_long_plans(self):
        template = TemplateRegistry.get("service_meetings")
        project = template.default_project
        project["meetings"] = [meeting_row(f"Termin {index}") for index in range(20)]

        self.assertEqual(len(template.renderer_class.render_pages(project)), 2)

    def test_field_service_groups_renderer_paginates_groups_and_long_lists(self):
        template = TemplateRegistry.get("field_service_groups")
        project = template.default_project
        project["groups"] = [
            group(f"GRUPA {index}", [member(f"Osoba {row}") for row in range(24 if index == 1 else 2)])
            for index in range(1, 7)
        ]

        pages = template.renderer_class.render_pages(project)

        self.assertEqual(len(pages), 3)


class RendererTests(unittest.TestCase):
    def test_every_template_exports_pdf_and_jpg(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for template in TemplateRegistry.all():
                pdf_path = root / f"{template.id}.pdf"
                jpg_path = root / f"{template.id}.jpg"

                template.renderer_class.export_pdf(str(pdf_path), template.default_project)
                template.renderer_class.export_jpg(str(jpg_path), template.default_project)

                self.assertGreater(pdf_path.stat().st_size, 500)
                self.assertGreater(jpg_path.stat().st_size, 500)


class CleaningAttendantsConflictTests(unittest.TestCase):
    def test_console_and_attendant_on_same_date_is_a_conflict(self):
        project = TemplateRegistry.get("cleaning_attendants").default_project
        project["weekly_assignments"] = [
            weekly_row("2026-06-10", "2026-06-14", console_person="Jan Test"),
        ]
        project["attendant_assignments"] = [
            attendant_row("2026-06-14", hall_attendant="Jan Test"),
        ]

        conflicts = find_conflicts(project)

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["date"], "2026-06-14")
        self.assertEqual(conflicts[0]["person"], "Jan Test")
        self.assertIn("konsola Zoom", conflicts[0]["roles"])
        self.assertIn("porządkowy sala", conflicts[0]["roles"])


class PeopleRoleTests(unittest.TestCase):
    def test_legacy_people_receive_all_roles(self):
        profiles = normalize_profiles(["Jan Test"], {})

        self.assertEqual(set(profiles["Jan Test"]), set(ALL_ROLES))

    def test_eligible_people_respect_assigned_role(self):
        people = ["Anna", "Jan", "Piotr"]
        profiles = {
            "Anna": ["console"],
            "Jan": ["service_conductor"],
            "Piotr": [],
        }

        self.assertEqual(eligible_people(people, profiles, "service_conductor"), ["Jan"])
        self.assertEqual(eligible_people(people, profiles, "console"), ["Anna"])


class GroupToolsTests(unittest.TestCase):
    def test_roman_and_numeric_group_names_match(self):
        self.assertEqual(normalize_group_name("I"), "1")
        self.assertEqual(normalize_group_name("GRUPA I"), "1")
        self.assertEqual(normalize_group_name("Grupa 1"), "1")

    def test_group_leader_is_read_from_latest_field_service_groups_project(self):
        older = TemplateRegistry.get("field_service_groups").default_project
        older["groups"][0]["members"] = [member("Starszy Grupowy", ROLE_LEADER)]
        latest = TemplateRegistry.get("field_service_groups").default_project
        latest["groups"][0]["members"] = [member("Aktualny Grupowy", ROLE_LEADER)]

        leaders, names = latest_group_leaders(
            [
                {"project": {"template_id": "cleaning_attendants"}},
                {"project": latest},
                {"project": older},
            ]
        )

        self.assertEqual(leaders["1"], "Aktualny Grupowy")
        self.assertEqual(names[0], "GRUPA 1")

    def test_custom_group_name_and_leader_are_preserved(self):
        project = {
            "template_id": "field_service_groups",
            "groups": [group("Północ", [member("Jan Test", ROLE_LEADER)])],
        }

        leaders, names = group_leaders_from_project(project)

        self.assertEqual(leaders["północ"], "Jan Test")
        self.assertEqual(names, ["Północ"])


class AssignmentToolsTests(unittest.TestCase):
    def test_recurring_dates_can_generate_selected_weekdays(self):
        dates = generate_recurring_dates(date(2026, 6, 1), date(2026, 6, 14), {2, 5, 6})

        self.assertEqual(
            dates,
            [
                date(2026, 6, 3),
                date(2026, 6, 6),
                date(2026, 6, 7),
                date(2026, 6, 10),
                date(2026, 6, 13),
                date(2026, 6, 14),
            ],
        )

    def test_assistant_uses_only_conductors_and_balances_assignments(self):
        people = ["Anna", "Jan", "Piotr"]
        profiles = {
            "Anna": ["service_conductor"],
            "Jan": ["service_conductor"],
            "Piotr": ["console"],
        }
        project = TemplateRegistry.get("service_meetings").default_project
        rows = build_service_meetings_plan(
            project,
            [date(2026, 6, day) for day in (2, 4, 6, 9, 11)],
            people,
            profiles,
            "17:15",
            "Sala",
        )
        assigned = [row["conductor"] for row in rows]

        self.assertNotIn("Piotr", assigned)
        self.assertNotEqual(assigned[0], assigned[1])
        self.assertLessEqual(abs(assigned.count("Anna") - assigned.count("Jan")), 1)

    def test_assistant_avoids_people_busy_in_open_project(self):
        current = TemplateRegistry.get("cleaning_attendants").default_project
        current["attendant_assignments"] = [attendant_row("2026-06-14", hall_attendant="Jan")]
        blocked = assigned_people_by_date(current)
        project = TemplateRegistry.get("service_meetings").default_project

        rows = build_service_meetings_plan(
            project,
            [date(2026, 6, 14)],
            ["Jan", "Anna"],
            {"Jan": ["service_conductor"], "Anna": ["service_conductor"]},
            "17:15",
            "Sala",
            blocked_people_by_date=blocked,
        )

        self.assertEqual(rows[0]["conductor"], "Anna")

    def test_dates_can_be_shifted_in_bulk(self):
        project = TemplateRegistry.get("cleaning_attendants").default_project
        project["weekly_assignments"] = [weekly_row("2026-06-10", "2026-06-14")]
        project["attendant_assignments"] = [attendant_row("2026-06-14")]

        changed = shift_project_dates(project, 7)

        self.assertEqual(changed, 3)
        self.assertEqual(project["weekly_assignments"][0]["start_date"], "2026-06-17")
        self.assertEqual(project["attendant_assignments"][0]["date"], "2026-06-21")

    def test_person_assignments_export_to_text_and_calendar(self):
        project = TemplateRegistry.get("service_meetings").default_project
        project["meetings"] = [
            meeting_row("2026-06-16", "17:15", "Sala Królestwa", "Jan Test"),
            meeting_row("2026-06-18", "17:15", "Zoom", "Anna Test"),
        ]

        self.assertEqual(len(person_assignments(project, "Jan Test")), 1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text_path = root / "jan.txt"
            calendar_path = root / "jan.ics"
            export_person_assignments(text_path, project, "Jan Test")
            export_ics(calendar_path, project, "Jan Test")

            text = text_path.read_text(encoding="utf-8")
            calendar = calendar_path.read_text(encoding="utf-8")

        self.assertIn("Prowadzenie zbiórki", text)
        self.assertIn("20260616", calendar)
        self.assertIn("Jan Test", calendar)
        self.assertNotIn("Anna Test", calendar)

    def test_archive_assignments_keep_project_title_and_filter_person(self):
        project = TemplateRegistry.get("service_meetings").default_project
        project["meetings"] = [meeting_row("14.06.2026", "17:15", "Sala", "Jan Test")]
        rows = archive_assignments([{"archive_id": "a1", "title": "Czerwiec", "project": project}])

        self.assertEqual(rows[0]["date"], "2026-06-14")
        self.assertEqual(rows[0]["project_title"], "Czerwiec")
        self.assertEqual(assignment_rows_for_person(rows, "jan test"), rows)


class ProjectArchiveTests(unittest.TestCase):
    def test_project_is_updated_in_one_archive_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = ProjectArchive(Path(directory))
            project = TemplateRegistry.get("service_meetings").default_project
            archive.save(project)
            project["meetings"].append(meeting_row("2026-06-14", conductor="Jan Test"))
            archive.save(project)

            entries = archive.load_entries()

        self.assertIn(ARCHIVE_ID_KEY, project)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["project"]["meetings"][0]["conductor"], "Jan Test")

    def test_archive_removes_entries_older_than_90_days(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = ProjectArchive(Path(directory), retention_days=90)
            project = TemplateRegistry.get("service_meetings").default_project
            entry = archive.save(project)
            entry["updated_at"] = (datetime(2026, 1, 1, tzinfo=UTC)).isoformat()
            ProjectIO._write_json(Path(directory) / f"{entry['archive_id']}.json", entry)

            removed = archive.cleanup(datetime(2026, 6, 14, tzinfo=UTC))

        self.assertEqual(removed, 1)


class ProjectHistoryTests(unittest.TestCase):
    def test_undo_and_redo_restore_project_snapshots(self):
        history = ProjectHistory()
        project = {"template_id": "service_meetings", "title": "A"}
        history.reset(project)
        project["title"] = "B"
        history.observe(project)
        project["title"] = "C"

        self.assertEqual(history.undo(project)["title"], "B")
        self.assertEqual(history.undo({"template_id": "service_meetings", "title": "B"})["title"], "A")
        self.assertEqual(history.redo()["title"], "B")


class ProjectValidationTests(unittest.TestCase):
    def test_validation_reports_missing_people_and_duplicate_duties(self):
        project = TemplateRegistry.get("service_meetings").default_project
        project["meetings"] = [
            meeting_row("2026-06-14", conductor="Jan Test"),
            meeting_row("2026-06-14", conductor="Jan Test"),
            meeting_row("2026-06-21"),
        ]

        messages = [issue["message"] for issue in validate_project(project)]

        self.assertTrue(any("nie ma prowadzącego" in message for message in messages))
        self.assertTrue(any("2 obowiązki" in message for message in messages))


class ProjectIOTests(unittest.TestCase):
    def test_bundled_people_library_and_sample_assignments_are_empty(self):
        root = Path(__file__).resolve().parents[1]
        bundled_people = json.loads((root / "data" / "people.json").read_text(encoding="utf-8"))
        sample_project = ProjectIO.load_project(root / "data" / "project.json")

        self.assertEqual(DEFAULT_PEOPLE, [])
        self.assertEqual(bundled_people, [])
        self.assertEqual(extract_assignments(sample_project), [])

    def test_people_json_import_merges_and_skips_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "people.json"
            path.write_text(json.dumps({"people": ["Anna Nowak", "jan test", ""]}), encoding="utf-8")

            people, added = ProjectIO.import_people(path, ["Jan Test"])

        self.assertEqual(people, ["Jan Test", "Anna Nowak"])
        self.assertEqual(added, 1)

    def test_people_json_import_rejects_invalid_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "people.json"
            path.write_text(json.dumps({"names": ["Anna Nowak"]}), encoding="utf-8")

            with self.assertRaises(ValueError):
                ProjectIO.import_people(path)

    def test_people_library_export_and_import_preserves_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "library.json"
            ProjectIO.export_people_library(
                path,
                ["Jan Test", "Anna Test"],
                {
                    "Jan Test": ["console", "microphone"],
                    "Anna Test": ["service_conductor"],
                },
            )

            people, profiles, added, roles_updated = ProjectIO.import_people_library(path)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(people, ["Jan Test", "Anna Test"])
        self.assertEqual(profiles["Jan Test"], ["console", "microphone"])
        self.assertEqual(profiles["Anna Test"], ["service_conductor"])
        self.assertEqual(added, 2)
        self.assertEqual(roles_updated, 2)
        self.assertEqual(payload["format"], "planora_people_library")
        self.assertEqual(payload["people"][0]["roles"], ["console", "microphone"])

    def test_people_library_import_updates_roles_without_duplicating_names(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "library.json"
            path.write_text(
                json.dumps({"people": [{"name": "jan test", "roles": ["reader"]}]}),
                encoding="utf-8",
            )

            people, profiles, added, roles_updated = ProjectIO.import_people_library(
                path,
                ["Jan Test"],
                {"Jan Test": ["console"]},
            )

        self.assertEqual(people, ["Jan Test"])
        self.assertEqual(profiles["Jan Test"], ["reader"])
        self.assertEqual(added, 0)
        self.assertEqual(roles_updated, 1)

    def test_people_profiles_are_migrated_and_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            roles_path = Path(directory) / "people-roles.json"
            with patch("app.core.project_io.PEOPLE_ROLES_FILE", roles_path):
                profiles = ProjectIO.load_people_profiles(["Jan Test"])
                profiles["Jan Test"] = ["console"]
                ProjectIO.save_people_profiles(profiles)
                loaded = ProjectIO.load_people_profiles(["Jan Test"])

        self.assertEqual(loaded["Jan Test"], ["console"])

    def test_legacy_project_gets_default_template_id(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            path.write_text(json.dumps({"title": "Test", "weeks": []}), encoding="utf-8")

            project = ProjectIO.load_project(path)

        self.assertEqual(project["template_id"], "public_talk_watchtower")

    def test_cleaning_project_can_be_loaded_without_weeks_field(self):
        source = TemplateRegistry.get("cleaning_attendants").default_project
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cleaning.json"
            ProjectIO.save_project(path, source)

            project = ProjectIO.load_project(path)

        self.assertEqual(project["template_id"], "cleaning_attendants")
        self.assertEqual(len(project["weekly_assignments"]), 0)

    def test_midweek_project_can_be_saved_and_loaded(self):
        source = TemplateRegistry.get("midweek_meeting").default_project
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "midweek.json"
            ProjectIO.save_project(path, source)

            project = ProjectIO.load_project(path)

        self.assertEqual(project["template_id"], "midweek_meeting")
        self.assertEqual(len(project["meetings"]), 0)

    def test_field_service_groups_project_can_be_saved_and_loaded(self):
        source = TemplateRegistry.get("field_service_groups").default_project
        source["groups"][0]["members"].append(member("Jan Test", "leader"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "groups.json"
            ProjectIO.save_project(path, source)

            project = ProjectIO.load_project(path)

        self.assertEqual(project["template_id"], "field_service_groups")
        self.assertEqual(project["groups"][0]["members"][0]["role"], "leader")

    def test_service_meetings_project_can_be_saved_and_loaded(self):
        source = TemplateRegistry.get("service_meetings").default_project
        source["meetings"].append(meeting_row("Wtorek", "17:15", "Sala", "Jan Test", "#dbe7ee"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "service-meetings.json"
            ProjectIO.save_project(path, source)

            project = ProjectIO.load_project(path)

        self.assertEqual(project["template_id"], "service_meetings")
        self.assertEqual(project["meetings"][0]["place"], "Sala")


if __name__ == "__main__":
    unittest.main()
