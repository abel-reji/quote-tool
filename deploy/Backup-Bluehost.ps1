# Requires the authorized SSH key and pinned server host key. No credentials are exported.
$ErrorActionPreference = 'Stop'
$name = 'snapshot-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)
$hostName = 'finvestc@rnp.ywe.mybluehost.me'
$remoteRoot = '/home3/finvestc/quote-tool-private/backups'
$remotePath = "$remoteRoot/$name"
$localRoot = Join-Path $env:LOCALAPPDATA 'Quote Tool Backups\bluehost'
$localPath = Join-Path $localRoot $name
$sshOptions = @('-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
    '-o', 'ConnectTimeout=15', '-o', 'IdentitiesOnly=yes',
    '-i', (Join-Path $env:USERPROFILE '.ssh\bluehost_quote_staging_ed25519'))

$command = "umask 077 && /home3/finvestc/quote-tool-web/.venv/bin/python /home3/finvestc/quote-tool-web/quote_backup.py snapshot /home3/finvestc/quote-tool-private/data $remotePath"
& ssh @sshOptions $hostName $command
if ($LASTEXITCODE -ne 0) { throw 'Server snapshot failed. No off-server backup was recorded.' }

New-Item -ItemType Directory -Path $localRoot -Force | Out-Null
if (Test-Path -LiteralPath $localPath) { throw 'Backup destination already exists.' }
& scp @sshOptions -r "${hostName}:$remotePath" $localPath
if ($LASTEXITCODE -ne 0) { throw 'Download failed. The verified server copy remains available.' }

& py -3.11 (Join-Path $PSScriptRoot '..\quote_backup.py') verify $localPath
if ($LASTEXITCODE -ne 0) { throw 'Downloaded backup verification failed. Do not use this copy for recovery.' }
Write-Output "Verified off-server backup: $localPath"
Write-Output "Verified server backup: $remotePath"
# Deliberately no automatic deletion: retention can be added after measuring real backup sizes.
