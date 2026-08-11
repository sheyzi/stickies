# Sticky Notes

A simple, GNOME-native sticky notes app for the desktop. Built with **GTK4 + libadwaita** and **Python**, with zero extra dependencies beyond the standard GNOME stack.

It keeps your notes as little windows on the desktop, saves everything automatically, and even supports basic **markdown** formatting as you type.

## Features

- 🗒️ Multiple resizable, colorable notes that float on the desktop
- 📋 A **notes list page** — open/rename/delete notes without dumping them all on screen
- 🧠 **Remembers which notes were open** and restores only those on startup/login
- ✏️ **Live basic markdown**: headings, bold, italic, code, bullet & numbered lists
- 🎨 Per-note colors (yellow, blue, green, pink, purple, gray)
- 💾 **Autosaves** text, size and position to a local SQLite database
- 🚀 Runs again to focus the list / create notes; autostarts with your GNOME session

## Markdown

| You type         | You get        |
|------------------|----------------|
| `# Heading`      | Large heading  |
| `## Subheading`  | Medium heading |
| `### Heading`    | Small heading  |
| `**bold**`       | Bold text      |
| `*italic*`       | Italic text    |
| `` `code` ``     | Monospace code |
| `- item`         | Bullet list    |
| `1. item`        | Numbered list  |

Open the **Markdown Help** page from any note (⋮ menu) or the list (ⓘ button) to see a rendered example.

## Requirements

- **Fedora / GNOME** (primary target)
- Python 3, GTK4, libadwaita, PyGObject

On Fedora these are the packages the installer needs:

```
python3-gobject gtk4 libadwaita gtk3 desktop-file-utils librsvg2
```

## Install

### One-liner

```bash
curl -fsSL https://raw.githubusercontent.com/sheyzi/stickies/main/setup.sh | bash
```

### Manually (from a clone)

```bash
git clone https://github.com/sheyzi/stickies ~/stickies
bash ~/stickies/setup.sh
```

The installer:

1. Installs missing dependencies (`sudo dnf install ...`)
2. Clones the app to `~/.local/share/stickies/`
3. Installs the app icon
4. Adds a **Sticky Notes** launcher to the GNOME app grid
5. Adds an **autostart** entry so previously-open notes restore on login (skip with `--no-autostart`)

> Note: if you pipe the script through `curl | bash` and it needs `sudo`, run it again as
> `bash <(curl -fsSL URL/setup.sh)` from a terminal so `sudo` can prompt you.

## Usage

- Launch **Sticky Notes** from the app grid.
- If you had notes open last time, they reappear. Otherwise you get the **notes list**.
- **Right-click** a note → New Note / Notes List / Rename / Markdown Help / Color / Delete / Quit
- Click a note in the list to open it; **right-click** a row for Open / Rename / Delete
- Launch the app again while it's running to focus the notes list
- Double-click the note title area is not supported — use **Rename** in the menu

## Data

Everything is stored in a local SQLite database:

```
~/.stickynote/notes.sqlite
```

Notes, colors, sizes and open-state are saved automatically. Deleting the file resets the app (all notes gone) — keep a backup if you care.

### Migrating from Plum

If you previously used the *Plum* sticky notes app and have a `plum.sqlite` file, you can import your old notes:

```bash
python3 ~/.local/share/stickies/import_plum.py
```

## Uninstall

```bash
rm -rf ~/.local/share/stickies
rm -f ~/.local/share/applications/io.github.stickies.StickyNotes.desktop
rm -f ~/.config/autostart/stickies.desktop
rm -f ~/.local/share/icons/hicolor/scalable/apps/stickies.svg
# optionally remove your notes:
rm -rf ~/.stickynote
```

## License

[MIT](LICENSE)
