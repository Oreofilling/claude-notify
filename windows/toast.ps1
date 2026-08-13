# UTF-8 *with BOM* (PS 5.1 needs the BOM to read emoji/codepoints correctly).
# Modern popup (WinForms) — bypasses the toast banner subsystem.
# This machine suppresses toast banners system-wide, so we render a TopMost
# borderless window directly. Unicode title/body arrive as wide-string params
# via CreateProcessW from Python (notifier.py); in-file emoji are intentional.
#
# Layout: dark card (#1F2937) + left accent bar (category color) + emoji icon
#         + white title + light-gray body + close X. Rounded corners (Region),
#         slide-in + fade-in animation, custom WAV chime per category.
#
# Params (compatible with old notifier.py which passes -Scenario/-Silent):
#   -Category  stop | idle | permission | other   (decides color/icon/sound;
#              if absent, inferred from -Scenario: alarm=>permission, else stop)
#   -Scenario  "alarm" => legacy urgent marker
#   -Silent    1 => no sound
#   -Slot      stacking index (0=bottom); each popup offsets upward
param(
  [Parameter(Mandatory=$true)][string]$Title,
  [Parameter(Mandatory=$true)][string]$Body,
  [string]$Scenario = "",
  [string]$Loop     = "0",      # legacy, unused (urgent auto-loops its sound)
  [string]$Silent   = "0",
  [string]$Category = "",
  [int]$Slot = 0,
  [string]$Aumid = "ClaudeNotify.App"   # legacy, unused
)
$ErrorActionPreference = 'Stop'
trap {
  try { Add-Content -Path (Join-Path $env:TEMP 'cn_popup_err.log') -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $_.Exception.Message) } catch {}
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles() | Out-Null

# ---- resolve category -> icon / accent / sound ----
if ([string]::IsNullOrWhiteSpace($Category)) {
  $Category = if ($Scenario -eq 'alarm') { 'permission' } else { 'stop' }
}
$urgent = ($Category -eq 'permission')
$playSnd = ($Silent -ne '1')

switch ($Category) {
  'stop'       { $icon='✅'; $accent=[System.Drawing.Color]::FromArgb(34,197,94);   $snd='done' }
  'idle'       { $icon='💬'; $accent=[System.Drawing.Color]::FromArgb(245,158,11);  $snd='idle' }
  'permission' { $icon='🚨'; $accent=[System.Drawing.Color]::FromArgb(239,68,68);   $snd='urgent' }
  default      { $icon='🔔'; $accent=[System.Drawing.Color]::FromArgb(59,130,246);  $snd='idle' }
}
$bg     = [System.Drawing.Color]::FromArgb(31,41,55)     # gray-800 card
$txtW   = [System.Drawing.Color]::White
$txtGry = [System.Drawing.Color]::FromArgb(209,213,219)  # gray-300 body
$txtX   = [System.Drawing.Color]::FromArgb(156,163,175)  # gray-400 close

# ---- geometry (bottom-right, stacked) ----
$w = 380; $h = 118; $gap = 10
$sw = 1920; $sh = 1040
try { $sc = [System.Windows.Forms.Screen]::PrimaryScreen; if ($sc) { $wa = $sc.WorkingArea; $sw=[int]$wa.Width; $sh=[int]$wa.Height } } catch {}
$finalX = $sw - $w - 16
$finalY = $sh - $h - 12 - ($Slot * ($h + $gap))
if ($finalY -lt 4) { $finalY = 4 }

# ---- form ----
$form = New-Object System.Windows.Forms.Form
$form.FormBorderStyle = 'None'
$form.ControlBox      = $false
$form.Text            = ''
$form.StartPosition   = 'Manual'
$form.Size            = New-Object System.Drawing.Size($w, $h)
$form.TopMost         = $true
$form.ShowInTaskbar   = $false
$form.BackColor       = $bg
$form.Opacity         = 0.0
$form.Location        = New-Object System.Drawing.Point(($finalX + 70), $finalY)

# rounded corners via Region
$radius = 14
$gp = New-Object System.Drawing.Drawing2D.GraphicsPath
$gp.AddArc(0, 0, $radius, $radius, 180, 90)
$gp.AddArc(($w - $radius), 0, $radius, $radius, 270, 90)
$gp.AddArc(($w - $radius), ($h - $radius), $radius, $radius, 0, 90)
$gp.AddArc(0, ($h - $radius), $radius, $radius, 90, 90)
$gp.CloseAllFigures()
$form.Region = New-Object System.Drawing.Region($gp)

# ---- left accent bar ----
$bar = New-Object System.Windows.Forms.Panel
$bar.Location = New-Object System.Drawing.Point(0, 0)
$bar.Size     = New-Object System.Drawing.Size(6, $h)
$bar.BackColor = $accent
$form.Controls.Add($bar)

# ---- icon ----
$lblI = New-Object System.Windows.Forms.Label
$lblI.Text       = $icon
$lblI.Font       = New-Object System.Drawing.Font('Segoe UI Emoji', 16)
$lblI.ForeColor  = $txtW
$lblI.BackColor  = [System.Drawing.Color]::Transparent
$lblI.TextAlign  = [System.Drawing.ContentAlignment]::MiddleLeft
$lblI.Location   = New-Object System.Drawing.Point(16, 12)
$lblI.Size       = New-Object System.Drawing.Size(36, 40)
$form.Controls.Add($lblI)

# ---- title ----
$lblT = New-Object System.Windows.Forms.Label
$lblT.Text       = $Title
$lblT.Font       = New-Object System.Drawing.Font('Segoe UI', 12, [System.Drawing.FontStyle]::Bold)
$lblT.ForeColor  = $txtW
$lblT.BackColor  = [System.Drawing.Color]::Transparent
$lblT.TextAlign  = [System.Drawing.ContentAlignment]::MiddleLeft
$lblT.AutoEllipsis = $true
$lblT.Location   = New-Object System.Drawing.Point(56, 12)
$lblT.Size       = New-Object System.Drawing.Size(($w - 92), 30)
$form.Controls.Add($lblT)

# ---- close X ----
$lblX = New-Object System.Windows.Forms.Label
$lblX.Text       = [char]0x2715
$lblX.Font       = New-Object System.Drawing.Font('Segoe UI', 11)
$lblX.ForeColor  = $txtX
$lblX.BackColor  = [System.Drawing.Color]::Transparent
$lblX.TextAlign  = [System.Drawing.ContentAlignment]::MiddleCenter
$lblX.Location   = New-Object System.Drawing.Point(($w - 30), 8)
$lblX.Size       = New-Object System.Drawing.Size(24, 24)
$lblX.Cursor     = [System.Windows.Forms.Cursors]::Hand
$lblX.Add_MouseEnter({ $lblX.ForeColor = $txtW })
$lblX.Add_MouseLeave({ $lblX.ForeColor = $txtX })
$form.Controls.Add($lblX)

# ---- body ----
$lblB = New-Object System.Windows.Forms.Label
$lblB.Text       = $Body
$lblB.Font       = New-Object System.Drawing.Font('Segoe UI', 9.5)
$lblB.ForeColor  = $txtGry
$lblB.BackColor  = [System.Drawing.Color]::Transparent
$lblB.TextAlign  = [System.Drawing.ContentAlignment]::TopLeft
$lblB.AutoEllipsis = $true
$lblB.Location   = New-Object System.Drawing.Point(56, 44)
$lblB.Size       = New-Object System.Drawing.Size(($w - 80), ($h - 52))
$form.Controls.Add($lblB)

# ---- sound ----
$sound = $null
if ($playSnd) {
  $wav = Join-Path $PSScriptRoot ('sounds\' + $snd + '.wav')
  if (Test-Path $wav) {
    $sound = New-Object System.Media.SoundPlayer $wav
    if ($urgent) { $sound.PlayLooping() } else { $sound.Play() }
  } elseif ($urgent) { [System.Media.SystemSounds]::Exclamation.Play() }
  else { [System.Media.SystemSounds]::Asterisk.Play() }
}

# ---- timers: slide/fade-in, and auto-close (non-urgent) ----
$anim   = New-Object System.Windows.Forms.Timer
$closer = New-Object System.Windows.Forms.Timer
$anim.Interval   = 15
$closer.Interval = 7000
$offX = 70; $fadeMs = 220   # 动画时长(ms)；用真实经过时间驱动，避免跨 tick 计数器作用域陷阱

$stopAll = {
  if ($sound)  { $sound.Stop() }
  if ($anim)   { $anim.Stop() }
  if ($closer) { $closer.Stop() }
}
$close = {
  & $stopAll
  $form.Close()
}

$anim.Add_Tick({
  # 用真实经过时间驱动 fade/slide：只“读”脚本作用域变量，不做跨 tick 自增，
  # 彻底规避 PowerShell 事件 ScriptBlock 里 $x++ 不持久化的陷阱（否则 Opacity 永远≈0）。
  $elapsed = ((Get-Date) - $script:animStart).TotalMilliseconds
  $t = [Math]::Min(1.0, $elapsed / $fadeMs)
  $ease = $t * $t * (3 - 2 * $t)          # smoothstep
  $form.Opacity = $ease
  $nx = [int][Math]::Round($finalX + (1 - $ease) * $offX)
  $form.Location = New-Object System.Drawing.Point($nx, $finalY)
  if ($t -ge 1.0) {
    $form.Opacity = 1.0
    $form.Location = New-Object System.Drawing.Point($finalX, $finalY)
    $anim.Stop()
  }
})
$closer.Add_Tick($close)

$form.Add_Shown({
  $script:animStart = Get-Date      # 记录动画起点（只在 Shown 写一次，tick 里只读）
  $anim.Start()
  if (-not $urgent) { $closer.Start() }
})

# click anywhere = dismiss
$form.Add_Click($close)
$lblT.Add_Click($close)
$lblB.Add_Click($close)
$lblI.Add_Click($close)
$lblX.Add_Click($close)
$bar.Add_Click($close)

[void]$form.ShowDialog()
& $stopAll
