```
https://moddingcartel.com/static/cartelpack/cartelpack.zip
https://files.obnoxious.lol/switch (Visit here for SuperZip & HATS pack releases) (Extract to microsd & Create emunand in hekate ezpz)

This is a software pack that distributes:

cartelpack/moddingcartel.exe: USB & FTP extension of moddingcartel.com, it allows you to send games from the website to your switch. (Developed by me)
cartelpack/nsusbloader_installer.exe: NS USBLoader (Developed by ____)
cartelpack/nswdrivers.exe: Nintendo Switch USB Drivers (Developed by ___)
cartelpack/switch/sphaira: Nintendo Switch hbmenu replacement + installer + launcher + homebrew menu all in one, ftpd etc, required for switch to install games (Developed by ____)
cartelpack/switch/tinwoo: Nintendo Switch http+usb+network+usbhdd etc installer (Developed by _____)


1. Install cartelpack/nswdrivers.exe ( May need to reboot after for USBC install method )
2. Connect your nintendo switch to the same network as your PC (PC can be ethernet or wifi as long as same network, Switch as well) (IF PLAN TO USE FTP YOU WONT NEED TO REBOOT 100%)
3. Go into Hekate on your NSW & Mount SD card to PC OR turn off your NSW take out the microsd and use a microsd to usb or pc with a microsd reader or a phone etc
4. Copy & paste or extract this zip onto the microsd (You need to have SuperZip OR HATS pack installed properly already)
5. Open Sphaira (Applet mode in sphaira actually works decently, Its fine to use it to install a small game to then launch it in game mode)
If you dont know how to use game mode, you open a game while holding R on the right joycon. It'll open hbmenu or sphaira.
If it opened hbmenu, open sphaira. If sphaira isnt there you didnt put the files onto your microsd properly.
You can open hbmenu and then sphaira by pressing the Album button at the bottom, in Sphaira u can replace hbmenu entirely (Recommended)
6. Enable USBC & FTP install (Navigate Sphaira menus, Y -> Menu -> FTP Install -> Enable -> FTP Install again, or same thing with USBC install)
7. Ensure Sphaira is ready to receive files and youre in the USB or FTP install menu
8. Run moddingcartel.exe, this will ask you to sign in
9. Signup on moddingcartel.com (just user+pass, no email or sms etc, free)
10. Sign in using those details (just press enter when it asks for website/hostname)
11. When prompted for Switch IP, enter it manually OR press Enter to auto-scan (scans 192.168.*.* and 10.0.*.* ranges)
12. If ready, start sending games to your switch via moddingcartel.com

OPTIONAL+READ EXTRA:
13. Config file (config.yaml) and log files are now stored in the same directory as moddingcartel.exe
14. The app will verify your Switch IP on launch - if it's unreachable, it will automatically rescan
15. If it says " Ready! Start adding games to the queue... " either USB or FTP mode was detected to be working properly
16. If it crashes neither one is working properly, ensure you have drivers installed & ensure PC + Switch on same network
17. You can manually change the switch IP Address in the config.yaml if needed (It automatically scans 192.168.*.* and 10.0.*.* ranges)
18. The log file (send_to_switch.log) is located in the same directory as moddingcartel.exe - you can view it to debug problems
19. When built as an exe, the window will stay open on error so you can read the error message - press Enter to close
```