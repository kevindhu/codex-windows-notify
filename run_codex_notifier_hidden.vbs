Set shell = CreateObject("WScript.Shell")
command = "cmd /c cd /d ""C:\Users\lemondoo\PROJECTS\windows-notify-codex"" && pythonw.exe ""C:\Users\lemondoo\PROJECTS\windows-notify-codex\codex_notify.py"""
shell.Run command, 0, False
