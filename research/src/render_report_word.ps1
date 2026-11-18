param(
    [string]$InputDocx = (Join-Path $PSScriptRoot '..\results\FoodSave_Laporan_Perbandingan_Model.docx'),
    [string]$OutputPdf = (Join-Path $PSScriptRoot '..\results\evaluation\report_qa.pdf')
)
# Alternatif render Windows jika renderer LibreOffice tidak tersedia.
# Hanya membuka salinan laporan hasil tugas secara read-only, tanpa UI terlihat.
$ErrorActionPreference = 'Stop'
$sourcePath = [System.IO.Path]::GetFullPath($InputDocx)
$pdfPath = [System.IO.Path]::GetFullPath($OutputPdf)
New-Item -ItemType Directory -Path ([System.IO.Path]::GetDirectoryName($pdfPath)) -Force | Out-Null
$wordApp = $null
$reportDoc = $null
try {
    $wordApp = New-Object -ComObject Word.Application
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $reportDoc = $wordApp.Documents.Open($sourcePath, $false, $true)
    $reportDoc.ExportAsFixedFormat($pdfPath, 17)
    Write-Output $pdfPath
} finally {
    if ($null -ne $reportDoc) {
        $reportDoc.Close($false)
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($reportDoc)
    }
    if ($null -ne $wordApp) {
        $wordApp.Quit()
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordApp)
    }
}
