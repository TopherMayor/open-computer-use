#!/usr/bin/env python3
"""GTK3 fixture app for desktop tests."""

import sys

try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, Gdk
except ImportError:
    print("GTK3 not available", file=sys.stderr)
    sys.exit(1)


class DesktopTestApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.gsd.desktoptest")
        self.counter = 0
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        window = Gtk.ApplicationWindow(application=self, title="Desktop Test App")
        window.set_default_size(400, 300)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)

        self.label = Gtk.Label(label="0")
        self.label.set_name("counter")

        button = Gtk.Button(label="Increment")
        button.set_name("increment")
        button.connect("clicked", self.on_increment)

        self.name_entry = Gtk.Entry()
        self.name_entry.set_placeholder_text("Name")
        self.name_entry.set_name("name")

        scrolled = Gtk.ScrolledWindow()
        self.list_store = Gtk.ListStore(int, str)
        for i in range(50):
            self.list_store.append([i, f"Row {i}"])

        tree_view = Gtk.TreeView(model=self.list_store)
        tree_view.set_name("scrollable_list")
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Items", renderer, text=1)
        tree_view.append_column(column)
        scrolled.add(tree_view)

        menu_bar = Gtk.MenuBar()
        file_menu = Gtk.MenuItem(label="File")
        menu_bar.append(file_menu)
        submenu = Gtk.Menu()
        file_menu.set_submenu(submenu)
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self.on_quit)
        submenu.append(quit_item)

        vbox.pack_start(menu_bar, expand=False, fill=False, padding=0)
        vbox.pack_start(self.label, expand=False, fill=False, padding=0)
        vbox.pack_start(button, expand=False, fill=False, padding=0)
        vbox.pack_start(self.name_entry, expand=False, fill=False, padding=0)
        vbox.pack_start(scrolled, expand=True, fill=True, padding=0)

        window.add(vbox)
        window.show_all()

    def on_increment(self, button):
        self.counter += 1
        self.label.set_text(str(self.counter))

    def on_quit(self, item):
        self.quit()


def main():
    app = DesktopTestApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())