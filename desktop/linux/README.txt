FlexWeek for Linux
==================

FlexWeek plans your homework around school and sports, then tells you why
something moved. Everything it needs is inside this folder. You do not need
Python, a server or an internet connection.


Start FlexWeek
--------------
1. Open this FlexWeek folder.
2. Double-click the file named FlexWeek.
   If your file manager opens it as text or asks what to do, choose Run.
   Or open a terminal in this folder and type:  ./FlexWeek
3. A window opens. Choose Create account. The first account on this computer
   starts with a short setup: school hours, a sport, then your first homework.


Add FlexWeek to your app menu (optional)
----------------------------------------
Open a terminal in this folder and type:

    ./install-menu-entry.sh

FlexWeek then shows up in your app menu with its icon. Keep this folder where
it is afterwards. To remove the menu entry, type:

    ./install-menu-entry.sh --uninstall


Closing FlexWeek
----------------
Closing the window keeps FlexWeek running in the system tray, so reminders and
alarms still work. The first time, a message says so. To quit, right-click the
FlexWeek icon in the tray and choose Quit.

If your desktop has no system tray, closing the window quits FlexWeek.
Starting FlexWeek while it is already running brings its window back.


What your computer needs
------------------------
- A 64-bit Linux desktop: GNOME, KDE Plasma, Cinnamon, Xfce or similar.
- glibc 2.38 or newer. That means Ubuntu 24.04 or newer, Linux Mint 22 or
  newer, Debian 13 or newer, or Fedora 39 or newer.
- Working graphics (OpenGL or EGL). A remote or headless session without a
  display will not work.

Normal desktops already have everything else. The X11 cursor helpers FlexWeek
needs (libxcb-cursor and friends) are included in this folder.

@WEB_VERSION@


Your data
---------
Your accounts and weeks are saved on this computer in:

    ~/.local/share/FlexWeek

Deleting or replacing this FlexWeek folder does not delete them.


If FlexWeek does not start
--------------------------
Open a terminal in this folder and type ./FlexWeek to see the error.

- "GLIBC_2.38 not found": this Linux is older than FlexWeek supports.
  @WEB_FALLBACK@
- "error while loading shared libraries": a desktop library is missing. On
  Ubuntu, Mint or Debian install it with:
      sudo apt install libnss3 libxkbcommon-x11-0 libegl1 libgl1
  On Fedora:
      sudo dnf install nss libxkbcommon-x11 mesa-libEGL mesa-libGL
- "Chromium sandbox unavailable": this is expected on Ubuntu 24.04 and newer.
  FlexWeek turns the browser sandbox off because Ubuntu blocks it for apps
  without a security profile. FlexWeek only shows its own pages; other links
  open in your normal browser.


License
-------
FlexWeek is free software under the GNU GPL version 3 (see LICENSE.txt).
The files in licenses/ cover the X11 libraries included in this folder.
