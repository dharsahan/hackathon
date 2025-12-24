import unittest
from unittest.mock import MagicMock, patch
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Mock Kivy
# We need to make sure App class is usable
class MockApp:
    def run(self): pass
    def build(self): pass

sys.modules['kivy'] = MagicMock()
kivy_app_module = MagicMock()
kivy_app_module.App = MockApp
sys.modules['kivy.app'] = kivy_app_module

sys.modules['kivy.uix.boxlayout'] = MagicMock()
sys.modules['kivy.uix.button'] = MagicMock()
sys.modules['kivy.uix.label'] = MagicMock()
sys.modules['kivy.uix.scrollview'] = MagicMock()
sys.modules['kivy.uix.textinput'] = MagicMock()
sys.modules['kivy.uix.filechooser'] = MagicMock()
sys.modules['kivy.uix.popup'] = MagicMock()
sys.modules['kivy.uix.spinner'] = MagicMock()
sys.modules['kivy.clock'] = MagicMock()
sys.modules['kivy.utils'] = MagicMock()
sys.modules['android'] = MagicMock()
sys.modules['android.permissions'] = MagicMock()

# Import the app to test
# We need to import main as a module, but 'android' is also a system module name often used in Kivy/Buildozer environments
# and we have a folder named 'android'.
# To avoid conflict, we will import directly from file path or rename the folder for test purposes?
# Or just use relative import if possible.

import importlib.util
spec = importlib.util.spec_from_file_location("main", os.path.join(os.path.dirname(__file__), "../main.py"))
android_main = importlib.util.module_from_spec(spec)
sys.modules["main"] = android_main
spec.loader.exec_module(android_main)
OrganizerApp = android_main.OrganizerApp

# from android.main import OrganizerApp

class TestAndroidApp(unittest.TestCase):
    def setUp(self):
        # We need to mock the build method or super init because OrganizerApp inherits from App
        # Kivy App.__init__ does a lot of stuff.
        # But since we mocked kivy.app.App, OrganizerApp inherits from MagicMock.
        # So __init__ is MagicMock's init.

        self.app = OrganizerApp()

        # When mocking App, we need to ensure attributes we use exist
        self.app.status_log = MagicMock()
        self.app.path_input = MagicMock()

    def test_app_build(self):
        """Test that the app builds the UI."""
        layout = self.app.build()
        self.assertTrue(layout)

    @patch('main.Config')
    @patch('main.RulesEngine')
    @patch('main.FileOperations')
    @patch('main.Tier1Classifier')
    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.iterdir')
    def test_run_organizer(self, mock_iterdir, mock_exists, MockClassifier, MockFileOps, MockRulesEngine, MockConfig):
        """Test the organizer logic."""
        # Setup mocks
        mock_file = MagicMock()
        mock_file.is_file.return_value = True
        mock_file.name = "test.txt"

        mock_iterdir.return_value = [mock_file]

        # Mock engine behaviors
        engine_instance = MockRulesEngine.return_value
        engine_instance.evaluate.return_value = None # No custom rule match

        classifier_instance = MockClassifier.return_value
        classification_result = MagicMock()
        classification_result.category.value = "Documents"
        classification_result.subcategory = None
        classifier_instance.classify.return_value = classification_result

        file_ops_instance = MockFileOps.return_value
        file_ops_instance.get_destination_path.return_value = Path("/tmp/dest")
        file_ops_instance.move_file.return_value = Path("/tmp/dest/test.txt")

        # Run
        self.app.run_organizer("/tmp/test")

        # Verify
        MockConfig.load.assert_called()
        MockRulesEngine.assert_called()
        engine_instance.evaluate.assert_called_with(mock_file)
        classifier_instance.classify.assert_called_with(mock_file)
        file_ops_instance.move_file.assert_called()

    def test_start_organization_no_path(self):
        """Test validation when no path selected."""
        self.app.path_input.text = ""
        self.app.start_organization(None)
        # Should verify log called, but log is mocked poorly above because it's set in build()
        # which isn't called here unless we call build manually or mock status_log better.
        # But we mocked status_log in setUp.
        # Since status_log is a Mock, accessing .text += ... is actually a get then set on property.
        # Easier to check if we printed to log.
        # Wait, self.app.log calls self.status_log.text += ...

        # Actually checking if self.log was called is hard because we didn't mock self.log
        # But we can check if threading was NOT started.
        with patch('threading.Thread') as mock_thread:
            self.app.start_organization(None)
            mock_thread.assert_not_called()

if __name__ == '__main__':
    unittest.main()
