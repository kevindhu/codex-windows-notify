Option Explicit

Dim shell
Dim fileSystem
Dim repoRoot
Dim scriptPath
Dim pythonwPath
Dim command

Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

repoRoot = "__REPO_ROOT__"
If repoRoot = "__REPO_ROOT__" Then
    repoRoot = "C:\Users\lemondoo\PROJECTS\windows-notify-codex"
End If

scriptPath = repoRoot & "\codex_notify.py"
pythonwPath = "__PYTHONW__"
If pythonwPath = "__PYTHONW__" Then
    pythonwPath = "pythonw.exe"
End If

If Not fileSystem.FileExists(scriptPath) Then
    WScript.Quit 2
End If

shell.CurrentDirectory = repoRoot
command = """" & pythonwPath & """ """ & scriptPath & """"
shell.Run command, 0, False
