# P0-3 pre-check: read today's calendar and today's Sent Items subjects from classic Outlook over COM.
# This is the same COM interface MWB's collector will use through comtypes, so a security prompt here
# would also appear there. Prints counts and timings only, never subjects or names.
# If Outlook wasn't running, it is closed again at the end.
# Usage: powershell -NoProfile -File p0_3_outlook.ps1      (-Show also prints the subjects, on screen only)
param([switch]$Show)

$wasRunning = [bool](Get-Process OUTLOOK -ErrorAction SilentlyContinue)
$t0 = Get-Date
$ol = New-Object -ComObject Outlook.Application
$ns = $ol.GetNamespace('MAPI')
$tConnect = ((Get-Date) - $t0).TotalSeconds

$today = (Get-Date).Date
# Restrict parses dates in the Windows regional format (dd-MM-yyyy on en-IN), not the US one:
# a US-format filter silently matched nothing on 12 Oct. 'g' is the current short date and time.
$filter = "[Start] < '$($today.AddDays(1).ToString('g'))' AND [End] > '$($today.ToString('g'))'"

$t1 = Get-Date
$cal = $ns.GetDefaultFolder(9).Items          # 9 = olFolderCalendar
$cal.IncludeRecurrences = $true
$cal.Sort('[Start]')
$meetings = @($cal.Restrict($filter))
$withLink = @($meetings | Where-Object { "$($_.Location) $($_.Body)" -match 'teams\.microsoft\.com|zoom\.us|meet\.google\.com|webex\.com' }).Count
$tCal = ((Get-Date) - $t1).TotalSeconds

$t2 = Get-Date
$sent = $ns.GetDefaultFolder(5).Items         # 5 = olFolderSentMail
$sent.Sort('[SentOn]', $true)
$sentToday = @($sent.Restrict("[SentOn] >= '$($today.ToString('g'))'"))
$newestSent = $sent.GetFirst().SentOn
# With nothing sent today, read the 5 newest instead so the subject read is still tested.
$readFrom = if ($sentToday.Count) { $sentToday } else { @($sent | Select-Object -First 5) }
$subjects = @($readFrom | ForEach-Object { $_.Subject })
$tSent = ((Get-Date) - $t2).TotalSeconds

[pscustomobject]@{
    OutlookWasRunning   = $wasRunning
    ConnectSeconds      = [math]::Round($tConnect, 2)
    CalendarItemsToday  = $meetings.Count
    WithMeetingLink     = $withLink
    CalendarSeconds     = [math]::Round($tCal, 2)
    SentToday           = $sentToday.Count
    SubjectsRead        = @($subjects | Where-Object { $_ -ne $null }).Count
    NewestSentDay       = $newestSent.ToString('yyyy-MM-dd')
    SentSeconds         = [math]::Round($tSent, 2)
} | Format-List

if ($Show) { $meetings | ForEach-Object { "{0:HH:mm}  {1}" -f $_.Start, $_.Subject }; $subjects }

if (-not $wasRunning) { $ol.Quit() }
[void][Runtime.InteropServices.Marshal]::ReleaseComObject($ol)
