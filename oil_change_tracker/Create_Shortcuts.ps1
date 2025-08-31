
$base = "$env:LOCALAPPDATA\OilChangeTracker"
$ws = New-Object -ComObject WScript.Shell

# Desktop shortcut
$desktop = [Environment]::GetFolderPath('Desktop')
$link = $ws.CreateShortcut("$desktop\Oil Change Tracker.lnk")
$link.TargetPath = "$base\Run_Local_NoPython.bat"
$link.WorkingDirectory = $base
$link.IconLocation = "$env:SystemRoot\System32\shell32.dll, 167"
$link.Save()

# Start Menu shortcut
$startMenu = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"
$link2 = $ws.CreateShortcut("$startMenu\Oil Change Tracker.lnk")
$link2.TargetPath = "$base\Run_Local_NoPython.bat"
$link2.WorkingDirectory = $base
$link2.IconLocation = "$env:SystemRoot\System32\shell32.dll, 167"
$link2.Save()
