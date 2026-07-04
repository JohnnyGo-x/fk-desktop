import importlib.util
import os
import sys

if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
    from fk.desktop import desktop
    # Re-execute desktop module's code with __name__ == "__main__"
    desktop_path = os.path.join(os.path.dirname(__file__), "desktop.py")
    spec = importlib.util.spec_from_file_location("__main__", desktop_path)
    module = importlib.util.module_from_spec(spec)
    # Preserve already-imported fk.desktop.desktop globals
    module.__dict__.update(desktop.__dict__)
    spec.loader.exec_module(module)
