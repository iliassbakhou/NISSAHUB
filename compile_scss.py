# compile_scss.py
import subprocess
import time
import os
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

SCSS_DIR = os.path.join(os.path.dirname(__file__), 'static', 'scss')
CSS_DIR = os.path.join(os.path.dirname(__file__), 'static', 'css')
MAIN_SCSS_FILE = os.path.join(SCSS_DIR, 'main.scss')
OUTPUT_CSS_FILE = os.path.join(CSS_DIR, 'main.css')

os.makedirs(CSS_DIR, exist_ok=True)

def compile_scss_with_cli(event_path=None):
    if event_path:
        print(f"Change detected in '{os.path.basename(event_path)}'. Recompiling...")
    else:
        print("Initial SCSS compilation...")
    command = [ "sass", f"{MAIN_SCSS_FILE}:{OUTPUT_CSS_FILE}", "--style=expanded", "--source-map" ]
    try:
        is_windows = sys.platform.startswith('win')
        result = subprocess.run(command, capture_output=True, text=True, check=True, shell=is_windows)
        if result.stderr:
            print(f"Compilation warning:\n{result.stderr}")
        print(f"✅ Success! SCSS compiled with sourcemap.")
    except FileNotFoundError:
        print("❌ Error: 'sass' command not found. Have you run 'pip install -r requirements.txt' and activated your venv?")
    except subprocess.CalledProcessError as e:
        print("\n" + "="*50 + "\n❌ SCSS Compilation Failed!\n" + f"   Error: {e.stderr}" + "\n" + "="*50 + "\n")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

class ScssChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.scss'):
            compile_scss_with_cli(event.src_path)

if __name__ == "__main__":
    compile_scss_with_cli()
    print(f"Watching for SCSS changes in: {SCSS_DIR}")
    event_handler = ScssChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, SCSS_DIR, recursive=True)
    observer.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\nWatcher stopped.")
    finally:
        observer.stop()
        observer.join()