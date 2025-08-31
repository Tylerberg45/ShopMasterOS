Add-Type -Namespace Util -Name SleepGuard -MemberDefinition @"
    using System;
    using System.Runtime.InteropServices;
    public static class SleepGuard {
        [DllImport("kernel32.dll")]
        public static extern uint SetThreadExecutionState(uint esFlags);
    }
"@
$ES_CONTINUOUS = 0x80000000
$ES_SYSTEM_REQUIRED = 0x00000001
$ES_DISPLAY_REQUIRED = 0x00000002
try {
    while ($true) {
        [Util.SleepGuard]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED -bor $ES_DISPLAY_REQUIRED) | Out-Null
        Start-Sleep -Seconds 30
    }
} finally {
    [Util.SleepGuard]::SetThreadExecutionState($ES_CONTINUOUS) | Out-Null
}
