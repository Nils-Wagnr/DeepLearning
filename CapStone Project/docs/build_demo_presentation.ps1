param(
    [string]$DocsDirectory = $PSScriptRoot
)

$ErrorActionPreference = "Stop"
$docs = [System.IO.Path]::GetFullPath($DocsDirectory)
$sourceDeck = Join-Path $docs "ClaimGuard_Capstone_Praesentation_DE.pptx"
$outputDeck = Join-Path $docs "ClaimGuard_Capstone_Praesentation_DE_mit_UI_Demo.pptx"
$outputPdf = Join-Path $docs "ClaimGuard_Capstone_Praesentation_DE_mit_UI_Demo.pdf"
$videoSource = Join-Path $docs "ClaimGuard_UI_Demo_Source.pptx"
$video = Join-Path $docs "ClaimGuard_UI_Demo.mp4"
$framesDirectory = Join-Path $docs "demo_frames"

$expectedDocs = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "."))
if ($docs -ne $expectedDocs) {
    throw "Refusing to write outside the expected docs directory: $docs"
}
if (-not (Test-Path -LiteralPath $sourceDeck)) {
    throw "Source presentation not found: $sourceDeck"
}

$frames = @(
    @{ Path = (Join-Path $framesDirectory "01_upload.png"); Seconds = 3 },
    @{ Path = (Join-Path $framesDirectory "02_overview.png"); Seconds = 5 },
    @{ Path = (Join-Path $framesDirectory "04_comparison_setup.png"); Seconds = 4 },
    @{ Path = (Join-Path $framesDirectory "05_comparison_summary.png"); Seconds = 8 }
)
foreach ($frame in $frames) {
    if (-not (Test-Path -LiteralPath $frame.Path)) {
        throw "Demo frame not found: $($frame.Path)"
    }
}

foreach ($generated in @($outputDeck, $outputPdf, $videoSource, $video)) {
    $resolvedParent = [System.IO.Path]::GetFullPath((Split-Path -Parent $generated))
    if ($resolvedParent -ne $expectedDocs) {
        throw "Refusing to replace unexpected path: $generated"
    }
    if (Test-Path -LiteralPath $generated) {
        Remove-Item -LiteralPath $generated -Force
    }
}

$powerPoint = $null
$videoDeck = $null
$targetDeck = $null
try {
    $powerPoint = New-Object -ComObject PowerPoint.Application
    $powerPoint.Visible = -1

    # Build a timed slide sequence and let PowerPoint encode the MP4. This avoids
    # introducing a separate video toolchain and keeps the demo reproducible.
    $videoDeck = $powerPoint.Presentations.Add()
    $videoDeck.PageSetup.SlideWidth = 960
    $videoDeck.PageSetup.SlideHeight = 540
    foreach ($frame in $frames) {
        $slide = $videoDeck.Slides.Add($videoDeck.Slides.Count + 1, 12)
        $null = $slide.Shapes.AddPicture($frame.Path, 0, -1, 0, 0, 960, 540)
        $slide.SlideShowTransition.AdvanceOnTime = -1
        $slide.SlideShowTransition.AdvanceTime = [double]$frame.Seconds
    }
    $videoDeck.SaveAs($videoSource, 24)
    $videoDeck.CreateVideo($video, $true, 4, 720, 30, 85)

    $deadline = (Get-Date).AddMinutes(6)
    while ($videoDeck.CreateVideoStatus -in @(1, 2)) {
        if ((Get-Date) -gt $deadline) {
            throw "Timed out while PowerPoint was creating the demo video."
        }
        Start-Sleep -Seconds 2
    }
    if ($videoDeck.CreateVideoStatus -ne 3 -or -not (Test-Path -LiteralPath $video)) {
        throw "PowerPoint video creation failed with status $($videoDeck.CreateVideoStatus)."
    }
    $videoDeck.Close()
    $videoDeck = $null
    if (Test-Path -LiteralPath $videoSource) {
        Remove-Item -LiteralPath $videoSource -Force
    }

    Copy-Item -LiteralPath $sourceDeck -Destination $outputDeck
    $targetDeck = $powerPoint.Presentations.Open($outputDeck, 0, 0, 1)
    $demoSlide = $targetDeck.Slides.Item(6)

    # The video fills the slide and starts automatically in slideshow mode.
    $media = $demoSlide.Shapes.AddMediaObject2(
        $video,
        0,
        -1,
        0,
        0,
        $targetDeck.PageSetup.SlideWidth,
        $targetDeck.PageSetup.SlideHeight
    )
    $media.AnimationSettings.PlaySettings.PlayOnEntry = -1
    $media.AnimationSettings.PlaySettings.HideWhileNotPlaying = 0
    $media.AnimationSettings.PlaySettings.LoopUntilStopped = 0
    $media.MediaFormat.SetDisplayPictureFromFile($frames[0].Path)

    $label = $demoSlide.Shapes.AddShape(5, 648, 16, 278, 34)
    $label.Fill.ForeColor.RGB = 15132390
    $label.Fill.Transparency = 0.08
    $label.Line.Visible = 0
    $label.TextFrame.TextRange.Text = "UI-DEMO  |  20 SEKUNDEN  |  AUTOSTART"
    $label.TextFrame.TextRange.Font.Name = "Aptos"
    $label.TextFrame.TextRange.Font.Size = 12
    $label.TextFrame.TextRange.Font.Bold = -1
    $label.TextFrame.TextRange.Font.Color.RGB = 16777215
    $label.TextFrame.TextRange.ParagraphFormat.Alignment = 2

    $speakerNote = @"
Nick — 45 Sekunden
Das Video startet automatisch. Zuerst wird der echte RQ5-Bericht hochgeladen und lokal analysiert. Im Überblick nur kurz auf Prüfbedarf und die methodenunabhängigen Dokumentkennzahlen zeigen. Danach wechselt die Demo in den Modellvergleich: Heuristik und Ollama erhalten dieselben Claims und dieselbe Evidenz. Abweichungen sind kein automatischer Fehlernachweis, sondern gezielte Stellen für die menschliche Prüfung. Falls das Video nicht startet, das beiliegende ClaimGuard_UI_Demo.mp4 öffnen oder die statische Originalfolie verwenden.
"@
    foreach ($shape in $demoSlide.NotesPage.Shapes) {
        if ($shape.HasTextFrame -and $shape.TextFrame.HasText) {
            $existing = $shape.TextFrame.TextRange.Text
            if ($existing -like "Nick*" -or $existing -like "*90 Sekunden*") {
                $shape.TextFrame.TextRange.Text = $speakerNote.Trim()
            }
        }
    }

    $targetDeck.Save()
    $targetDeck.SaveAs($outputPdf, 32)
    $targetDeck.Close()
    $targetDeck = $null

    Write-Output "Created video: $video"
    Write-Output "Created presentation: $outputDeck"
    Write-Output "Created PDF fallback: $outputPdf"
}
finally {
    if ($targetDeck -ne $null) { $targetDeck.Close() }
    if ($videoDeck -ne $null) { $videoDeck.Close() }
    if ($powerPoint -ne $null) {
        $powerPoint.Quit()
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($powerPoint)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
