import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.project_io import ProjectIO
from app.core.template_registry import TemplateRegistry
from app.core.updater import UpdateChecker, UpdateCheckError
from app.templates.cleaning_attendants.conflicts import find_conflicts
from app.templates.cleaning_attendants.default_project import attendant_row, weekly_row
from app.gui.theme_manager import THEMES, build_stylesheet


class UpdateCheckerTests(unittest.TestCase):
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


class ThemeTests(unittest.TestCase):
    def test_multiple_themes_and_custom_accent_are_available(self):
        self.assertGreaterEqual(len(THEMES), 5)
        stylesheet = build_stylesheet({"theme": "graphite", "accent_color": "#123456", "font_scale": 120})
        self.assertIn("#123456", stylesheet)
        self.assertIn("QPushButton", stylesheet)


class TemplateRegistryTests(unittest.TestCase):
    def test_new_projects_start_without_schedule_entries(self):
        self.assertEqual(TemplateRegistry.get("public_talk_watchtower").default_project["weeks"], [])
        self.assertEqual(TemplateRegistry.get("cleaning_attendants").default_project["weekly_assignments"], [])
        self.assertEqual(TemplateRegistry.get("cleaning_attendants").default_project["attendant_assignments"], [])
        self.assertEqual(TemplateRegistry.get("midweek_meeting").default_project["meetings"], [])

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


class ProjectIOTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
