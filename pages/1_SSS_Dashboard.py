"""
pages/1_SSS_Dashboard.py
Runs the existing Jersey Mike's Same Store Sales dashboard.
"""
import os, sys

# Point to repo root so all imports in dashboard.py resolve correctly
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root)
os.chdir(root)

with open(os.path.join(root, "dashboard.py"), encoding="utf-8") as _f:
    exec(_f.read(), {"__name__": "__main__", "__file__": os.path.join(root, "dashboard.py")})
