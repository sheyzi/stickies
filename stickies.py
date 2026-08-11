#!/usr/bin/env python3
"""Sticky Notes — a simple GNOME-native notes app (GTK4 + libadwaita).

Run it again while running to focus the notes list page.
"""

import re

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")

from gi.repository import Adw, Gdk, GLib, Gtk, Pango

import stickydb

DEFAULT_WIDTH = 280
DEFAULT_HEIGHT = 280
SAVE_DEBOUNCE_MS = 300

COLORS = {
    "yellow": "#fff9c4",
    "blue": "#bbdefb",
    "green": "#c8e6c9",
    "pink": "#f8bbd0",
    "purple": "#e1bee7",
    "gray": "#e0e0e0",
}
HEADER_SHADES = {
    "yellow": "#f2e391",
    "blue": "#9fcdf6",
    "green": "#addcaf",
    "pink": "#f3a8c2",
    "purple": "#d8a7e1",
    "gray": "#cbcbcb",
}
COLOR_NAMES = list(COLORS)


def _first_line(text):
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def display_title(note):
    if note.get("Title"):
        return note["Title"]
    line = _first_line(note.get("Text"))
    return line[:60] if line else "Untitled"


def snippet_of(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return ""
    first = lines[0]
    rest = " ".join(lines[1:])
    combined = first + (" | " + rest if rest else "")
    return combined[:100]


def _find_closer(text, start, delim):
    """Find a closing delimiter with sanity guards. Returns -1 if none."""
    close = text.find(delim, start + len(delim))
    if close == -1 or close - start > 200:
        return -1
    open_end = start + len(delim)
    if open_end < len(text) and text[open_end].isspace():
        return -1
    if text[close - 1].isspace():
        return -1
    return close


def _scan_inline(text, base):
    """Return (start, end, kind) ranges for inline formatting within ``text``."""
    ranges = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "`":
            close = text.find("`", i + 1)
            if close != -1 and close - i <= 200:
                ranges.append((base + i, base + close + 1, "code"))
                i = close + 1
                continue
        elif c == "*":
            if i + 1 < n and text[i + 1] == "*":
                close = _find_closer(text, i, "**")
                if close != -1:
                    ranges.append((base + i, base + close + 2, "bold"))
                    i = close + 2
                    continue
            else:
                close = _find_closer(text, i, "*")
                if close != -1:
                    ranges.append((base + i, base + close + 1, "italic"))
                    i = close + 1
                    continue
        i += 1
    return ranges


def parse_markdown(text):
    """Parse basic markdown, returning (start, end, kind) ranges into ``text``."""
    ranges = []
    offset = 0
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\n")
        match = re.match(r"^(#{1,3})\s+", content)
        if match:
            kind = {1: "h1", 2: "h2", 3: "h3"}[len(match.group(1))]
            ranges.append((offset, offset + len(content), kind))
        elif re.match(r"^([-*]|\d+[.)])\s+", content):
            ranges.append((offset, offset + len(content), "list"))
        ranges.extend(_scan_inline(content, offset))
        offset += len(line)
    return ranges


def install_global_css():
    lines = []
    for name, bg in COLORS.items():
        header = HEADER_SHADES[name]
        lines.append(f".swatch-{name} {{ background-color: {bg}; border-radius: 3px; }}")
        lines.append(f".note-{name} {{ background-color: {bg}; }}")
        lines.append(f".note-{name} .top-bar {{ background-color: {header}; }}")
        lines.append(f".note-{name} headerbar {{ background-color: {header}; }}")
        lines.append(f".note-{name} label.heading {{ color: #141414; }}")
        lines.append(f".note-{name} menubutton > button {{ color: #141414; }}")
        lines.append(f".note-{name} windowcontrols {{ color: #141414; }}")
        lines.append(
            f".note-{name} textview {{ background-color: transparent; "
            f"caret-color: #141414; }}"
        )
        lines.append(
            f".note-{name} textview text, .note-{name} textview > text "
            f"{{ background-color: transparent; color: #141414; }}"
        )
        lines.append(
            f".note-{name} textview > text > selection "
            f"{{ background-color: rgba(0, 0, 0, 0.18); color: #141414; }}"
        )
    css = "\n".join(lines)
    provider = Gtk.CssProvider()
    provider.load_from_string(css)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
    )


def create_md_tags(buffer):
    return {
        "h1": buffer.create_tag("md-h1", weight=Pango.Weight.BOLD, scale=1.5),
        "h2": buffer.create_tag("md-h2", weight=Pango.Weight.BOLD, scale=1.3),
        "h3": buffer.create_tag("md-h3", weight=Pango.Weight.BOLD, scale=1.15),
        "list": buffer.create_tag("md-list", left_margin=14),
        "bold": buffer.create_tag("md-bold", weight=Pango.Weight.BOLD),
        "italic": buffer.create_tag("md-italic", style=Pango.Style.ITALIC),
        "code": buffer.create_tag("md-code", font="Monospace"),
    }


def apply_markdown(buffer, tags, text):
    """Set buffer text and apply basic markdown tags (display-only)."""
    buffer.set_text(text)
    start, end = buffer.get_bounds()
    buffer.remove_all_tags(start, end)
    for begin, finish, kind in parse_markdown(text):
        tag = tags.get(kind)
        if tag is not None:
            buffer.apply_tag(
                tag, buffer.get_iter_at_offset(begin), buffer.get_iter_at_offset(finish)
            )


def show_markdown_help(parent):
    win = Adw.Window(application=parent.get_application())
    win.set_title("Markdown Help")
    win.set_transient_for(parent)
    win.set_modal(True)
    win.set_default_size(480, 580)
    win.set_size_request(420, 420)

    toolbar = Adw.ToolbarView()
    header = Adw.HeaderBar()
    header.set_centering_policy(Adw.CenteringPolicy.STRICT)
    title = Gtk.Label(label="Markdown Help")
    title.add_css_class("title")
    header.set_title_widget(title)
    toolbar.add_top_bar(header)
    win.set_content(toolbar)

    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    toolbar.set_content(scroll)

    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    content.set_margin_top(16)
    content.set_margin_bottom(16)
    content.set_margin_start(20)
    content.set_margin_end(20)
    scroll.set_child(content)

    section = Gtk.Label(label="Rendered Example")
    section.add_css_class("heading")
    section.set_halign(Gtk.Align.START)
    content.append(section)

    buffer = Gtk.TextBuffer()
    tags = create_md_tags(buffer)
    apply_markdown(
        buffer,
        tags,
        "# Heading\n"
        "## Subheading\n"
        "### Smaller heading\n\n"
        "**bold** and *italic* and `inline code`\n\n"
        "- bullet item\n"
        "- another item\n\n"
        "1. numbered item\n"
        "2. second item\n",
    )
    example = Gtk.TextView()
    example.set_buffer(buffer)
    example.set_editable(False)
    example.set_cursor_visible(False)
    example.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    example.set_size_request(0, 230)
    frame = Gtk.Frame()
    frame.set_child(example)
    content.append(frame)

    section = Gtk.Label(label="Syntax")
    section.add_css_class("heading")
    section.set_halign(Gtk.Align.START)
    content.append(section)

    syntax_rows = [
        ("# Heading", "Large heading"),
        ("## Subheading", "Medium heading"),
        ("### Heading", "Small heading"),
        ("**bold**", "Bold text"),
        ("*italic*", "Italic text"),
        ("`code`", "Monospace code"),
        ("- item", "Bullet list"),
        ("1. item", "Numbered list"),
    ]
    for syntax, desc in syntax_rows:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        code = Gtk.Label(label=syntax)
        code.add_css_class("monospace")
        code.set_halign(Gtk.Align.START)
        code.set_xalign(0)
        code.set_width_chars(14)
        desc_label = Gtk.Label(label=desc)
        desc_label.set_halign(Gtk.Align.START)
        desc_label.set_xalign(0)
        desc_label.set_hexpand(True)
        row.append(code)
        row.append(desc_label)
        content.append(row)

    win.present()


class NoteWindow(Adw.ApplicationWindow):
    def __init__(self, app, note):
        super().__init__(application=app)
        self.app = app
        self.note = note
        self._save_pending = False
        self._destroyed = False
        self._deleted = False

        self.set_default_size(
            note.get("Width") or DEFAULT_WIDTH, note.get("Height") or DEFAULT_HEIGHT
        )
        self.set_size_request(DEFAULT_WIDTH, DEFAULT_HEIGHT)
        self.set_title(self.display_title())

        toolbar = Adw.ToolbarView()
        self.set_content(toolbar)

        header = Adw.HeaderBar()
        header.set_centering_policy(Adw.CenteringPolicy.STRICT)
        toolbar.add_top_bar(header)

        self.title_label = Gtk.Label(label=self.display_title())
        self.title_label.add_css_class("heading")
        self.title_label.set_max_width_chars(20)
        self.title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_label.set_valign(Gtk.Align.CENTER)
        header.set_title_widget(self.title_label)

        self._menu_popover = Gtk.Popover()
        self._menu_popover.set_child(self._build_menu_box())
        self.menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic")
        self.menu_btn.set_tooltip_text("Note actions")
        self.menu_btn.set_popover(self._menu_popover)
        header.pack_end(self.menu_btn)

        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.textview.set_left_margin(10)
        self.textview.set_right_margin(10)
        self.textview.set_top_margin(8)
        self.textview.set_bottom_margin(8)
        self.buffer = self.textview.get_buffer()
        self.text_tag = self.buffer.create_tag("note-text", foreground="#141414")
        self.md_tags = create_md_tags(self.buffer)
        self.buffer.set_text(note.get("Text") or "")
        self._apply_text_tag()

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(self.textview)
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        toolbar.set_content(scroll)

        self._apply_color()

        self.buffer.connect("changed", self._on_text_changed)
        self.connect("close-request", self._on_close_request)
        self.connect("destroy", self._on_destroy)
        self.connect("notify::allocation", self._on_geometry_change)

        self.present()

    def display_title(self):
        return display_title(self.note)

    def _apply_text_tag(self):
        start, end = self.buffer.get_bounds()
        self.buffer.remove_all_tags(start, end)
        self.buffer.apply_tag(self.text_tag, start, end)
        text = self.buffer.get_text(start, end, False)
        for begin, finish, kind in parse_markdown(text):
            tag = self.md_tags.get(kind)
            if tag is None:
                continue
            self.buffer.apply_tag(
                tag, self.buffer.get_iter_at_offset(begin), self.buffer.get_iter_at_offset(finish)
            )

    def _apply_color(self):
        for name in COLOR_NAMES:
            self.remove_css_class("note-" + name)
        self.add_css_class("note-" + self.note["Color"])

    def _build_menu_box(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        box.set_margin_start(4)
        box.set_margin_end(4)

        def mk(icon_name, label, handler):
            btn = Gtk.Button()
            hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            hb.append(Gtk.Image(icon_name=icon_name))
            hb.append(Gtk.Label(label=label))
            btn.set_child(hb)
            btn.add_css_class("flat")
            btn.set_halign(Gtk.Align.FILL)
            btn.connect("clicked", handler)
            return btn

        pop = self._menu_popover

        box.append(mk("plus-symbolic", "New Note", lambda *_: self._close_menu_then(self.app.new_note)))
        box.append(mk("view-list-symbolic", "Notes List", lambda *_: self._close_menu_then(self.app.show_list)))
        box.append(mk("edit-rename-symbolic", "Rename", lambda *_: self._close_menu_then(self._show_rename)))
        box.append(mk("help-about-symbolic", "Markdown Help", lambda *_: self._close_menu_then(self._show_markdown_help)))
        box.append(Gtk.Separator())

        color_label = Gtk.Label(label="Color")
        color_label.add_css_class("dim-label")
        color_label.set_halign(Gtk.Align.START)
        box.append(color_label)

        color_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for name in COLOR_NAMES:
            sw = Gtk.Box()
            sw.set_size_request(22, 22)
            sw.set_valign(Gtk.Align.CENTER)
            sw.add_css_class("swatch-" + name)
            cb = Gtk.Button()
            cb.set_child(sw)
            cb.add_css_class("flat")
            cb.connect("clicked", self._on_pick_color, name)
            color_row.append(cb)
        box.append(color_row)

        box.append(Gtk.Separator())
        box.append(mk("user-trash-symbolic", "Delete", lambda *_: self._close_menu_then(self._confirm_delete)))
        box.append(Gtk.Separator())
        box.append(mk("window-close-symbolic", "Quit", self._quit))

        return box

    def _close_menu_then(self, fn):
        self._menu_popover.popdown()
        fn()

    def _show_markdown_help(self):
        show_markdown_help(self)

    def _on_pick_color(self, _btn, name):
        self.note["Color"] = name
        self._apply_color()
        self._schedule_save()
        self._menu_popover.popdown()
        self.app.refresh_list()

    def _on_title_edited(self, title):
        self.note["Title"] = title.strip()
        self.title_label.set_text(self.display_title())
        self.set_title(self.display_title())
        self._schedule_save()
        self.app.refresh_list()

    def _schedule_save(self):
        if self._save_pending:
            return
        self._save_pending = True
        GLib.timeout_add(SAVE_DEBOUNCE_MS, self._flush_save)

    def _capture_geometry(self):
        try:
            self.note["Width"] = self.get_width()
            self.note["Height"] = self.get_height()
        except Exception:
            pass

    def _flush_save(self):
        self._save_pending = False
        if self._destroyed:
            return False
        self._capture_geometry()
        start, end = self.buffer.get_start_iter(), self.buffer.get_end_iter()
        self.note["Text"] = self.buffer.get_text(start, end, False)
        stickydb.update_note(self.note)
        return False

    def _flush_save_now(self):
        if self._destroyed:
            return
        self._capture_geometry()
        start, end = self.buffer.get_start_iter(), self.buffer.get_end_iter()
        self.note["Text"] = self.buffer.get_text(start, end, False)
        stickydb.update_note(self.note)

    def _on_text_changed(self, _buffer):
        self._apply_text_tag()
        self._schedule_save()

    def _on_geometry_change(self, _widget, _pspec):
        self._schedule_save()

    def _on_close_request(self, *_args):
        self._flush_save_now()
        if not (self.app._quitting or self._deleted):
            stickydb.set_open(self.note["Id"], False)
            self.note["IsOpen"] = 0
        self.app.note_closed(self.note["Id"])
        return False

    def _on_destroy(self, *_args):
        self._destroyed = True
        self._flush_save_now()
        self.app.note_closed(self.note["Id"])

    def _confirm_delete(self):
        dialog = Adw.AlertDialog.new("Delete this note?", "This cannot be undone.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_delete_response)
        dialog.present(self)

    def _on_delete_response(self, dialog, response):
        if response == "delete":
            self.app.delete_note(self.note["Id"])

    def _show_rename(self):
        dialog = Adw.AlertDialog.new("Rename Note", "")
        entry = Gtk.Entry()
        entry.set_text(self.display_title())
        entry.set_activates_default(True)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("ok", "Rename")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("ok")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_rename_response, entry)
        dialog.present(self)

    def _on_rename_response(self, dialog, response, entry):
        if response == "ok":
            self._on_title_edited(entry.get_text())

    def _quit(self, *_args):
        self.app._quitting = True
        self.app.quit()


class ListWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.app = app
        self.set_title("Sticky Notes")
        self.set_default_size(420, 560)
        self.set_size_request(320, 360)

        toolbar = Adw.ToolbarView()
        self.set_content(toolbar)

        header = Adw.HeaderBar()
        header.set_centering_policy(Adw.CenteringPolicy.STRICT)
        title = Gtk.Label(label="Sticky Notes")
        title.add_css_class("title")
        header.set_title_widget(title)

        new_btn = Gtk.Button(icon_name="list-add-symbolic")
        new_btn.add_css_class("suggested-action")
        new_btn.set_tooltip_text("New Note")
        new_btn.connect("clicked", lambda *_: self.app.new_note())
        header.pack_end(new_btn)

        help_btn = Gtk.Button(icon_name="help-about-symbolic")
        help_btn.set_tooltip_text("Markdown Help")
        help_btn.connect("clicked", lambda *_: show_markdown_help(self))
        header.pack_end(help_btn)

        toolbar.add_top_bar(header)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        toolbar.set_content(self.stack)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.connect("row-activated", self._on_row_activated)
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.listbox)
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)
        self.stack.add_named(scroll, "list")

        gesture = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        gesture.connect("pressed", self._on_row_secondary_pressed)
        self.listbox.add_controller(gesture)

        status = Adw.StatusPage()
        status.set_icon_name("note-edit-symbolic")
        status.set_title("No Notes")
        status.set_description("Create your first sticky note")
        status_new = Gtk.Button(label="New Note")
        status_new.add_css_class("suggested-action")
        status_new.connect("clicked", lambda *_: self.app.new_note())
        status.set_child(status_new)
        self.stack.add_named(status, "empty")

        self.refresh()
        self.connect("destroy", self._on_destroy)
        self.present()

    def _on_destroy(self, *_args):
        if self.app.list_window is self:
            self.app.list_window = None

    def refresh(self):
        notes = stickydb.load_notes()
        self.listbox.remove_all()
        if not notes:
            self.stack.set_visible_child_name("empty")
            return
        self.stack.set_visible_child_name("list")
        for note in notes:
            self.listbox.append(self._build_row(note))

    def _build_row(self, note):
        row = Gtk.ListBoxRow()
        row._note_id = note["Id"]
        hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        hb.set_margin_top(8)
        hb.set_margin_bottom(8)
        hb.set_margin_start(12)
        hb.set_margin_end(12)

        swatch = Gtk.Box()
        swatch.set_size_request(14, 14)
        swatch.set_valign(Gtk.Align.CENTER)
        swatch.add_css_class("swatch-" + note["Color"])
        hb.append(swatch)

        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        vb.set_hexpand(True)
        vb.set_valign(Gtk.Align.CENTER)

        title = Gtk.Label(label=display_title(note))
        title.add_css_class("heading")
        title.set_halign(Gtk.Align.START)
        title.set_max_width_chars(48)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        vb.append(title)

        snippet = Gtk.Label(label=snippet_of(note["Text"]))
        snippet.add_css_class("dim-label")
        snippet.set_halign(Gtk.Align.START)
        snippet.set_max_width_chars(48)
        snippet.set_ellipsize(Pango.EllipsizeMode.END)
        vb.append(snippet)

        hb.append(vb)

        if note["IsOpen"]:
            icon = Gtk.Image(icon_name="check-round-outline-symbolic")
            icon.add_css_class("dim-label")
            hb.append(icon)

        row.set_child(hb)
        return row

    def _row_note(self, row):
        note_id = getattr(row, "_note_id", None)
        for note in stickydb.load_notes():
            if note["Id"] == note_id:
                return note
        return None

    def _on_row_activated(self, _listbox, row):
        note = self._row_note(row)
        if note is None:
            return
        stickydb.set_open(note["Id"], True)
        note["IsOpen"] = 1
        self.app.open_note(note)

    def _on_row_secondary_pressed(self, gesture, _n_press, _x, y):
        row = self.listbox.get_row_at_y(y)
        if row is None:
            return
        note = self._row_note(row)
        if note is None:
            return
        pop = Gtk.Popover()
        pop.set_relative_to(row)
        pop.set_position(Gtk.PositionType.BOTTOM)
        pop.set_child(self._build_row_menu(note))
        pop.present()

    def _build_row_menu(self, note):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        box.set_margin_start(4)
        box.set_margin_end(4)

        def mk(label, handler):
            btn = Gtk.Button(label=label)
            btn.add_css_class("flat")
            btn.set_halign(Gtk.Align.FILL)
            btn.connect("clicked", handler)
            return btn

        box.append(mk("Open", lambda *_e, n=note: self._open_note(n)))
        box.append(mk("Rename", lambda *_e, n=note: self._show_rename(n)))
        box.append(Gtk.Separator())
        box.append(mk("Delete", lambda *_e, n=note: self._confirm_delete(n)))
        return box

    def _open_note(self, note):
        stickydb.set_open(note["Id"], True)
        note["IsOpen"] = 1
        self.app.open_note(note)

    def _show_rename(self, note):
        dialog = Adw.AlertDialog.new("Rename Note", "")
        entry = Gtk.Entry()
        entry.set_text(display_title(note))
        entry.set_activates_default(True)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("ok", "Rename")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("ok")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_rename_response, note, entry)
        dialog.present(self)

    def _on_rename_response(self, dialog, response, note, entry):
        if response == "ok":
            note["Title"] = entry.get_text().strip()
            stickydb.update_note(note)
            win = self.app.note_windows.get(note["Id"])
            if win is not None:
                win.note["Title"] = note["Title"]
                win.title_label.set_text(win.display_title())
            self.refresh()

    def _confirm_delete(self, note):
        dialog = Adw.AlertDialog.new("Delete this note?", "This cannot be undone.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_delete_response, note["Id"])
        dialog.present(self)

    def _on_delete_response(self, dialog, response, note_id):
        if response == "delete":
            self.app.delete_note(note_id)


class StickyApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.stickies.StickyNotes")
        self._activated = False
        self._quitting = False
        self.list_window = None
        self.note_windows = {}

    def do_startup(self):
        Adw.Application.do_startup(self)
        stickydb.init_db()
        Gtk.Window.set_default_icon_name("stickies")

    def do_activate(self):
        if not self._activated:
            self._activated = True
            notes = stickydb.load_notes()
            open_notes = [note for note in notes if note.get("IsOpen")]
            if open_notes:
                for note in open_notes:
                    self.open_note(note)
            else:
                self.show_list()
        else:
            self.show_list()

    def new_note(self):
        note = stickydb.create_note(is_open=True)
        self.open_note(note)
        self.refresh_list()

    def open_note(self, note):
        existing = self.note_windows.get(note["Id"])
        if existing is not None:
            existing.present()
            return
        self.note_windows[note["Id"]] = NoteWindow(self, note)

    def note_closed(self, note_id):
        self.note_windows.pop(note_id, None)
        self.refresh_list()

    def delete_note(self, note_id):
        stickydb.delete_note(note_id)
        win = self.note_windows.pop(note_id, None)
        if win is not None:
            win._deleted = True
            win.close()
        self.refresh_list()

    def refresh_list(self):
        if self.list_window is not None:
            self.list_window.refresh()

    def show_list(self):
        if self.list_window is None:
            self.list_window = ListWindow(self)
        else:
            self.list_window.present()


def main():
    Adw.init()
    install_global_css()
    app = StickyApp()
    app.run(None)


if __name__ == "__main__":
    main()
