#! /bin/sh

# network_use - Display wifi transfer rate in a graph
# Copyright (C) 2016, Amir Livne Bar-on
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


ask() {
    echo -n "\n$1 [y/N] "
    read response
    case $response in
        y|Y|yes|Yes|YES) break ;;
        *) exit 0 ;;
    esac
}

echo "Setting up a menu entry for the network_use.py script..."

if [ -z "$XDG_CURRENT_DESKTOP" ]; then
    ask "\
This system does not appear to conform to the Free Desktop\n\
Specification (e.g. Gnome, KDE, Xfce, Lxde). Do you want to\n\
continue with the installation anyway?"
fi

if [ ! -x "network_use.py" ]; then
    ask "\
The script network_use.py is not executable. Do you want to\n\
set it and continue with the installation?"
    chmod +x network_use.py || exit $?
fi

if [ ! -e "$HOME/.local/share/applications/" ]; then
    ask "\
The directory ~/.local/share/applications/ does not exist. Do\n\
you want to create it and continue with the installation?"
    mkdir -p "$HOME/.local/share/applications" || exit $?
fi

if [ -e "$HOME/.local/share/applications/network_use.desktop" ]; then
    ask "A desktop file for network_use already exists. Overwrite it?"
else
    ask "Create a menu entry for the script in its current location?"
fi

cat > "$HOME/.local/share/applications/network_use.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Network Usage Monitor
Icon=$(pwd)/network_use.png
Exec=$(pwd)/network_use.py
Comment=Show network usage by time in a graph
Categories=System
Terminal=false
EOF

echo "Added Network Usage Monitor to the System category in the applications menu."

