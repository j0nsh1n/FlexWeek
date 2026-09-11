FlexWeek for Windows
====================

FlexWeek plans your homework around school and sports, then tells you why
something moved. Everything it needs is installed with it. You do not need
Python, a server or an internet connection.


Install and start FlexWeek
--------------------------
1. Run FlexWeek-Windows-x64-Setup.exe. It installs FlexWeek for your Windows
   account and does not need an administrator. Tick "Create a desktop
   shortcut" if you want one.
2. If Windows shows "Windows protected your PC", choose More info, then
   Run anyway. See "Why Windows warns you" below.
3. Open FlexWeek from the Start menu. Choose Create account. A new account
   starts with a short setup: school hours, a sport, then your first homework.

Schools and IT: FlexWeek-Windows-x64.msi installs FlexWeek for every account on
the PC, in Program Files, and needs an administrator. Use one installer or the
other, not both.

To remove FlexWeek, open Settings, then Apps, then Installed apps, and
uninstall FlexWeek.


Why Windows warns you
---------------------
FlexWeek is not signed with a paid code-signing certificate yet, so Windows
SmartScreen does not recognize the publisher and warns about any new download.
The warning does not mean something harmful was found. The source code is public
on GitHub, and the release page lists a SHA-256 checksum for each installer if
you want to confirm the download is complete.


Closing FlexWeek
----------------
Closing the window keeps FlexWeek running in the notification area (near the
clock), so reminders and alarms still work. The first time, a message says so.
To quit, right-click the FlexWeek icon there and choose Quit. You may need to
click the small arrow to see hidden icons.

Starting FlexWeek while it is already running brings its window back.


What your computer needs
------------------------
- Windows 10 version 1809 or newer, or Windows 11, 64-bit.
- Working graphics (the same OpenGL/Direct3D a normal desktop already has).
  Unicode text support (ICU: icuuc and icuin) is part of Windows since 1703;
  FlexWeek does not ship a second copy of those Windows files.

@WEB_VERSION@


Your data
---------
Your accounts and weeks are saved on this computer in:

    %APPDATA%\FlexWeek

Uninstalling or reinstalling FlexWeek does not delete them.


License
-------
FlexWeek is free software under the GNU GPL version 3 (see LICENSE.txt).
