"""Pytest-Setup: das Projekt-Wurzelverzeichnis auf den Importpfad legen, damit
`import pet` / `import config` aus tests/ heraus funktionieren. Die Tests
brauchen kein pygame und kein Fenster — pet.py ist reine Logik."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
