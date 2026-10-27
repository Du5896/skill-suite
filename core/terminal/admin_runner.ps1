# Admin runner for terminal-commander: executed elevated via UAC (user clicks Yes).
# Receives the command as base64 to avoid any quoting/escaping mistakes.
param([string]$CmdB64,[string]$OutFile)
$ErrorActionPreference='Continue'
try{
  $cmd=[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($CmdB64))
  $out=Invoke-Expression $cmd 2>&1|Out-String
  $code=0
  if($LASTEXITCODE -ne $null){$code=$LASTEXITCODE}
  [pscustomobject]@{ok=$true;exit=$code;output=$out.Trim()}|ConvertTo-Json -Compress|Out-File -FilePath $OutFile -Encoding utf8
}catch{[pscustomobject]@{ok=$false;exit=1;output=$_.Exception.Message}|ConvertTo-Json -Compress|Out-File -FilePath $OutFile -Encoding utf8}
