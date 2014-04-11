Dim Shell, Shortcut, Fso
Set Shell = CreateObject("WScript.Shell")
Set Fso = CreateObject("Scripting.FileSystemObject")
Set Shortcut = Shell.CreateShortcut(Shell.SpecialFolders("Desktop") & "\Urlaubsplaner.lnk")
Shortcut.TargetPath = "C:\Python27\pythonw.exe"
Shortcut.WorkingDirectory = Fso.GetAbsolutePathName(".")
Shortcut.IconLocation = Fso.GetAbsolutePathName("holidays.ico")
Shortcut.Arguments = """" & Fso.GetAbsolutePathName("holidays.pyc") & """"
Shortcut.Save
