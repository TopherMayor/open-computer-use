#!/usr/bin/env python3
"""Test get_children() vs get_child_at_index() approaches."""
import gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi

try:
    Atspi.set_timeout(2000, 2000)
except TypeError:
    pass

desktop = Atspi.get_desktop(0)

# Get the app
app = desktop.get_child_at_index(0)
print(f"App: {app.get_name()}")

# Get the window
window = app.get_child_at_index(0)
print(f"Window: {window.get_name()} role={window.get_role_name()}")

# Test get_children() vs get_child_at_index()
print("\n--- window.get_children() ---")
try:
    children = window.get_children()
    print(f"get_children() returned: {type(children)} len={len(children) if children else 0}")
    if children:
        for c in children:
            print(f"  {c.get_name()} role={c.get_role_name()}")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n--- window.get_child_count() + get_child_at_index() ---")
n = window.get_child_count()
print(f"child count: {n}")
for i in range(n):
    child = window.get_child_at_index(i)
    if child:
        name = child.get_name() or ""
        role = child.get_role_name() or ""
        print(f"  [{i}] {name} role={role}")
        
        # Go deeper
        n2 = child.get_child_count()
        if n2 > 0:
            print(f"    has {n2} children:")
            for j in range(min(n2, 20)):
                gc = child.get_child_at_index(j)
                if gc:
                    gname = gc.get_name() or ""
                    grole = gc.get_role_name() or ""
                    n3 = gc.get_child_count()
                    print(f"    [{j}] {gname} role={grole} sub={n3}")
                    if grole == "scroll pane" and n3 > 0:
                        for k in range(min(n3, 10)):
                            sc = gc.get_child_at_index(k)
                            if sc:
                                print(f"      [{k}] {sc.get_name() or ''} role={sc.get_role_name() or ''}")
