__import__("sys").path.insert(0, ".")

import logging
from pathlib import Path
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.clock import Clock
from kivy.utils import platform

# On Android, we need to request permissions
if platform == "android":
    from android.permissions import request_permissions, Permission

    request_permissions(
        [Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_EXTERNAL_STORAGE]
    )

    # Request MANAGE_EXTERNAL_STORAGE for Android 11+
    # This requires user to go to settings, so we usually fire an intent.
    try:
        from jnius import autoclass
        from android import activity

        Environment = autoclass("android.os.Environment")
        if Environment.isExternalStorageManager():
            pass
        else:
            Intent = autoclass("android.content.Intent")
            Settings = autoclass("android.provider.Settings")
            Uri = autoclass("android.net.Uri")

            # API 30+
            if (
                Environment.isExternalStorageLegacy()
            ):  # Just a check, logic is complicated here
                pass

            # We try to open settings
            intent = Intent()
            intent.setAction(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
            package_uri = Uri.parse("package:" + activity.getPackageName())
            intent.setData(package_uri)
            activity.startActivity(intent)

    except Exception as e:
        print(f"Failed to request MANAGE_EXTERNAL_STORAGE: {e}")

# Import smart_file_organizer modules
# Note: In Buildozer, we need to ensure smart_file_organizer is in the path or packaged correctly.
# If this fails, we mock it for the test.
try:
    from smart_file_organizer.src.config import Config
    from smart_file_organizer.src.actions.rules_engine import RulesEngine
    from smart_file_organizer.src.actions.file_operations import FileOperations
    from smart_file_organizer.src.classification.tier1_metadata import Tier1Classifier
    from smart_file_organizer.src.config.categories import FileCategory
except ImportError:
    # Fallback for development/testing if structure is different
    import sys

    sys.path.append("..")
    from smart_file_organizer.src.config import Config
    from smart_file_organizer.src.actions.rules_engine import RulesEngine
    from smart_file_organizer.src.actions.file_operations import FileOperations
    from smart_file_organizer.src.classification.tier1_metadata import Tier1Classifier
    from smart_file_organizer.src.config.categories import FileCategory


class OrganizerApp(App):
    def build(self):
        self.title = "Smart File Organizer"

        # Main layout
        layout = BoxLayout(orientation="vertical", padding=10, spacing=10)

        # Header
        header = Label(
            text="Smart File Organizer", font_size=24, size_hint_y=None, height=50
        )
        layout.add_widget(header)

        # Path selection
        path_layout = BoxLayout(orientation="horizontal", size_hint_y=None, height=40)
        self.path_input = TextInput(
            text="/storage/emulated/0/Download", multiline=False
        )
        path_layout.add_widget(self.path_input)

        browse_btn = Button(text="Browse", size_hint_x=None, width=80)
        browse_btn.bind(on_release=self.show_file_chooser)
        path_layout.add_widget(browse_btn)

        layout.add_widget(path_layout)

        # Status area
        self.status_log = TextInput(readonly=True, size_hint_y=1)
        layout.add_widget(self.status_log)

        # Action button
        organize_btn = Button(text="Organize Now", size_hint_y=None, height=60)
        organize_btn.bind(on_release=self.start_organization)
        layout.add_widget(organize_btn)

        return layout

    def log(self, message):
        self.status_log.text += f"{message}\n"
        # Scroll to bottom? (Kivy TextInput usually handles this if cursor moved)

    def show_file_chooser(self, instance):
        content = BoxLayout(orientation="vertical")
        file_chooser = FileChooserIconView(path="/storage/emulated/0/")

        btn_layout = BoxLayout(size_hint_y=None, height=50)
        select_btn = Button(text="Select")
        cancel_btn = Button(text="Cancel")

        btn_layout.add_widget(select_btn)
        btn_layout.add_widget(cancel_btn)

        content.add_widget(file_chooser)
        content.add_widget(btn_layout)

        popup = Popup(title="Select Directory", content=content, size_hint=(0.9, 0.9))

        def select(instance):
            self.path_input.text = file_chooser.path
            popup.dismiss()

        select_btn.bind(on_release=select)
        cancel_btn.bind(on_release=popup.dismiss)

        popup.open()

    def start_organization(self, instance):
        target_dir = self.path_input.text
        if not target_dir:
            self.log("Please select a directory.")
            return

        self.log(f"Starting organization for: {target_dir}")

        # Run in background to avoid freezing UI
        import threading

        t = threading.Thread(target=self.run_organizer, args=(target_dir,))
        t.start()

    def run_organizer(self, target_dir):
        try:
            # We need to adapt the RulesEngine or Organization logic here.
            # The existing code likely expects a Config object.

            # Load config (might fail if config.yaml not found, so we should create default)
            try:
                config = Config.load(
                    Path(target_dir) / "config.yaml"
                )  # Try loading from target dir?
            except Exception:
                config = Config()  # Use defaults

            # Setup directories
            config.organization.base_directory = Path(target_dir) / "Organized"

            # Initialize engines
            rules_engine = RulesEngine(
                base_directory=config.organization.base_directory
            )
            file_ops = FileOperations(base_directory=config.organization.base_directory)
            classifier = Tier1Classifier()

            # Manually scan and organize
            target_path = Path(target_dir)
            if not target_path.exists():
                Clock.schedule_once(
                    lambda dt: self.log(f"Error: Path {target_dir} does not exist.")
                )
                return

            files = [f for f in target_path.iterdir() if f.is_file()]
            Clock.schedule_once(lambda dt: self.log(f"Found {len(files)} files."))

            count = 0
            for file_path in files:
                try:
                    Clock.schedule_once(
                        lambda dt, f=file_path: self.log(f"Processing {f.name}...")
                    )

                    # 1. Check custom rules
                    classification = rules_engine.evaluate(file_path)

                    # 2. If no rule matched, use Tier 1 classification (extension/mime)
                    if not classification:
                        classification = classifier.classify(file_path)

                    # 3. Move file
                    if classification:
                        category = (
                            classification.category.value
                            if hasattr(classification.category, "value")
                            else str(classification.category)
                        )
                        subcategory = classification.subcategory

                        dest_path = file_ops.get_destination_path(
                            category=category,
                            subcategory=subcategory,
                            use_date=config.organization.use_date_folders,
                        )

                        # Execute move
                        new_path = file_ops.move_file(file_path, dest_path)
                        Clock.schedule_once(
                            lambda dt, f=file_path.name, n=new_path: self.log(
                                f"Moved {f} -> {n}"
                            )
                        )
                        count += 1
                    else:
                        Clock.schedule_once(
                            lambda dt, f=file_path.name: self.log(
                                f"Skipped {f} (unknown)"
                            )
                        )

                except Exception as e:
                    Clock.schedule_once(
                        lambda dt, err=str(e): self.log(f"Error processing file: {err}")
                    )

            Clock.schedule_once(
                lambda dt, c=count: self.log(f"Organization complete. Moved {c} files.")
            )

            Clock.schedule_once(lambda dt: self.log("Organization complete."))

        except Exception as e:
            import traceback

            err = traceback.format_exc()
            Clock.schedule_once(lambda dt: self.log(f"Critical Error: {err}"))


if __name__ == "__main__":
    OrganizerApp().run()
