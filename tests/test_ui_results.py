"""Tests for Milestone 3 dynamic results UI and selection logic."""

import unittest

from PySide6.QtWidgets import QApplication

from core.models import DuplicateGroup, FileInfo, FileStatus, ScanStats
from widgets.duplicate_card import DuplicateCard
from widgets.results_container import ResultsContainer

# Ensure QApplication instance exists
app = QApplication.instance()
if not app:
    app = QApplication([])


class TestResultsUIAndSelection(unittest.TestCase):

    def setUp(self):
        # Create a sample duplicate group with 3 files
        self.f1 = FileInfo(path="C:/Downloads/a.txt", name="a.txt", size=1024, mtime=100.0, status=FileStatus.KEEP)
        self.f2 = FileInfo(path="C:/Downloads/Copy/a.txt", name="a.txt", size=1024, mtime=200.0, status=FileStatus.DUPLICATE)
        self.f3 = FileInfo(path="C:/Old/a_backup.txt", name="a_backup.txt", size=1024, mtime=50.0, status=FileStatus.DUPLICATE)

        self.group = DuplicateGroup(
            group_id="grp_1",
            group_name="a.txt",
            file_size=1024,
            sha256="abcdef123456",
            files=[self.f1, self.f2, self.f3],
        )

        self.stats = ScanStats(
            total_files_scanned=10,
            total_size_scanned_bytes=20480,
            duplicate_groups_count=1,
            duplicate_files_count=2,
            wasted_space_bytes=2048,
            duration_seconds=0.5,
        )

    def test_duplicate_card_keep_vs_duplicate_state(self):
        keep_card = DuplicateCard(self.f1.to_dict())
        self.assertIsNone(keep_card.checkbox)
        self.assertFalse(keep_card.is_selected_for_delete())

        dup_card = DuplicateCard(self.f2.to_dict())
        self.assertIsNotNone(dup_card.checkbox)
        self.assertTrue(dup_card.is_selected_for_delete())

        # Toggle deletion checkbox
        toggled_events = []
        dup_card.selection_changed.connect(lambda chk, data: toggled_events.append((chk, data)))
        dup_card.set_selected_for_delete(False)
        self.assertFalse(dup_card.is_selected_for_delete())
        self.assertEqual(len(toggled_events), 1)
        self.assertFalse(toggled_events[0][0])

    def test_results_container_empty_state_initially(self):
        container = ResultsContainer()
        self.assertEqual(len(container.selected_files), 0)
        self.assertEqual(container.action_bar.count_label.text(), "0 file(s) selected")
        self.assertFalse(container.action_bar.delete_button.isEnabled())

    def test_results_container_set_results_and_selection_tracking(self):
        container = ResultsContainer()
        container.set_results([self.group], self.stats)

        # Initial state: 2 duplicate files should be selected, 1 kept file is NOT selected
        self.assertEqual(len(container.selected_files), 2)
        self.assertIn(self.f2.path, container.selected_files)
        self.assertIn(self.f3.path, container.selected_files)
        self.assertNotIn(self.f1.path, container.selected_files)

        self.assertEqual(container.action_bar.count_label.text(), "2 file(s) selected")
        self.assertTrue(container.action_bar.delete_button.isEnabled())
        self.assertIn("2.00 KB", container.action_bar.size_label.text())

    def test_switch_retained_copy(self):
        container = ResultsContainer()
        container.set_results([self.group], self.stats)

        # Initially, f1 is KEEP, f2 and f3 are DUPLICATE
        self.assertEqual(self.f1.status, FileStatus.KEEP)

        # Switch keep to f2
        container._handle_switch_keep(self.group, self.f2.to_dict())

        self.assertEqual(self.f2.status, FileStatus.KEEP)
        self.assertEqual(self.f1.status, FileStatus.DUPLICATE)
        self.assertEqual(self.f3.status, FileStatus.DUPLICATE)

        # Now f1 and f3 must be selected for deletion, f2 must NOT be
        self.assertIn(self.f1.path, container.selected_files)
        self.assertIn(self.f3.path, container.selected_files)
        self.assertNotIn(self.f2.path, container.selected_files)
        self.assertEqual(len(container.selected_files), 2)

    def test_deselect_and_select_all_preserves_kept_file(self):
        container = ResultsContainer()
        container.set_results([self.group], self.stats)

        # Deselect All
        container.deselect_all_duplicates()
        self.assertEqual(len(container.selected_files), 0)
        self.assertEqual(container.action_bar.count_label.text(), "0 file(s) selected")
        self.assertFalse(container.action_bar.delete_button.isEnabled())

        # Select All Duplicates
        container.select_all_duplicates()
        # Only duplicates (f2, f3) selected; f1 is KEEP and never selected
        self.assertEqual(len(container.selected_files), 2)
        self.assertNotIn(self.f1.path, container.selected_files)

    def test_global_heuristics(self):
        container = ResultsContainer()
        container.set_results([self.group], self.stats)

        # Oldest mtime is f3 (50.0)
        container.apply_global_heuristic("oldest")
        self.assertEqual(self.f3.status, FileStatus.KEEP)
        self.assertNotIn(self.f3.path, container.selected_files)
        self.assertIn(self.f1.path, container.selected_files)
        self.assertIn(self.f2.path, container.selected_files)

        # Newest mtime is f2 (200.0)
        container.apply_global_heuristic("newest")
        self.assertEqual(self.f2.status, FileStatus.KEEP)
        self.assertNotIn(self.f2.path, container.selected_files)
        self.assertIn(self.f1.path, container.selected_files)

    def test_cancelled_and_error_states(self):
        container = ResultsContainer()
        container.show_cancelled_state(self.stats)
        self.assertEqual(container.heading.text(), "Scan Cancelled")

        container.show_error_state("Access violation reading disk sector")
        self.assertEqual(container.heading.text(), "Scan Failed")


if __name__ == "__main__":
    unittest.main()
