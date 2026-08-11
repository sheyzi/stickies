#!/usr/bin/env bash
#
# Sticky Notes installer
#
# Installs the app to ~/.local/share/stickies and wires up the
# application launcher, autostart entry and app icon.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/sheyzi/stickies/main/setup.sh | bash
#   bash setup.sh                 # from a local clone
#   REPO_URL=... bash setup.sh    # override the source repo
#   bash setup.sh --no-autostart  # skip the autostart entry
#
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/sheyzi/stickies}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/share/stickies}"
DATA_DIR="$HOME/.stickynote"
APP_ID="io.github.stickies.StickyNotes"
AUTOSTART=1

for arg in "$@"; do
    case "$arg" in
        --no-autostart) AUTOSTART=0 ;;
        -h|--help)
            grep '^#' "$0" | sed 's/^# \{0,1\}//' | head -30
            exit 0
            ;;
    esac
done

say()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

need_cmd() { command -v "$1" >/dev/null 2>&1; }

# ---------------------------------------------------------------------------
# 1. Dependencies
# ---------------------------------------------------------------------------
install_deps() {
    if need_cmd dnf; then
        local pkgs=(python3-gobject gtk4 libadwaita gtk3 desktop-file-utils librsvg2)
        local missing=()
        local p
        for p in "${pkgs[@]}"; do
            rpm -q "$p" >/dev/null 2>&1 || missing+=("$p")
        done
        if [[ ${#missing[@]} -gt 0 ]]; then
            say "Installing missing packages: ${missing[*]}"
            sudo dnf install -y "${missing[@]}" || die "sudo dnf failed. Run manually:\n  sudo dnf install -y ${missing[*]}"
        fi
    elif need_cmd apt-get; then
        say "Installing packages via apt (Debian/Ubuntu)"
        sudo apt-get update -y
        sudo apt-get install -y python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 \
            libgtk-4-1 libadwaita-1-0 librsvg2-common desktop-file-utils gtk-update-icon-cache
    else
        warn "No supported package manager found. Please install GTK4, libadwaita and PyGObject manually."
    fi
}

# ---------------------------------------------------------------------------
# 2. Fetch the app
# ---------------------------------------------------------------------------
fetch_app() {
    need_cmd git || die "git is required to fetch the app."
    say "Downloading Sticky Notes from $REPO_URL"
    local tmp="$INSTALL_DIR.tmp"
    rm -rf "$tmp"
    git clone --depth 1 "$REPO_URL" "$tmp" || die "Failed to clone $REPO_URL"
    rm -rf "$INSTALL_DIR"
    mv "$tmp" "$INSTALL_DIR"
    chmod +x "$INSTALL_DIR/stickies.py" "$INSTALL_DIR/import_windows_stickies.py"
}

# ---------------------------------------------------------------------------
# 3. Icon
# ---------------------------------------------------------------------------
install_icon() {
    local icons_dir="$HOME/.local/share/icons/hicolor/scalable/apps"
    mkdir -p "$icons_dir"
    cp "$INSTALL_DIR/assets/stickies.svg" "$icons_dir/stickies.svg"
    if need_cmd gtk-update-icon-cache; then
        gtk-update-icon-cache -f "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
    fi
}

# ---------------------------------------------------------------------------
# 4. Launcher + autostart
# ---------------------------------------------------------------------------
install_desktop() {
    mkdir -p "$HOME/.local/share/applications" "$HOME/.config/autostart"

    sed "s|@PATH@|$INSTALL_DIR|g" "$INSTALL_DIR/install/stickies.desktop.in" \
        > "$HOME/.local/share/applications/$APP_ID.desktop"
    say "Installed launcher: $HOME/.local/share/applications/$APP_ID.desktop"

    if [[ "$AUTOSTART" == "1" ]]; then
        sed "s|@PATH@|$INSTALL_DIR|g" "$INSTALL_DIR/install/autostart.desktop.in" \
            > "$HOME/.config/autostart/stickies.desktop"
        say "Installed autostart: $HOME/.config/autostart/stickies.desktop"
    else
        rm -f "$HOME/.config/autostart/stickies.desktop"
        say "Autostart entry removed"
    fi

    if need_cmd update-desktop-database; then
        update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
    fi
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
main() {
    install_deps
    fetch_app
    install_icon
    install_desktop

    say "Done! Sticky Notes is installed at $INSTALL_DIR"
    say "Launch it from the app grid, or run:"
    printf '      python3 %s\n' "$INSTALL_DIR/stickies.py"
    printf '\n  Data is stored in %s\n' "$DATA_DIR"
    printf '  The app restores previously-open notes on login.\n'
}

main "$@"
