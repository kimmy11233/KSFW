param([string]$ZipFile)

Add-Type -AssemblyName System.IO.Compression.FileSystem

$excludeExact = @('.env')
$exclude      = @('venv', '.vscode', '__pycache__', 'tmp', '.git')
$excludeContents = @('saves', 'Story Templates')
$source       = Get-Location

$zip = [System.IO.Compression.ZipFile]::Open($ZipFile, 'Create')

# Add empty entries for the content-excluded directories so they appear in the zip
$excludeContents | ForEach-Object {
    $dirPath = Join-Path $source $_
    if (Test-Path $dirPath) {
        $zip.CreateEntry("$_/") | Out-Null
    }
}

Get-ChildItem -Recurse | Where-Object {
    $item = $_
    $name = $item.Name
    -not $item.PSIsContainer -and
    -not ($excludeExact | Where-Object { $name -eq $_ }) -and
    -not ($exclude | Where-Object { $item.FullName -match [regex]::Escape($_) }) -and
    -not ($excludeContents | Where-Object { $item.FullName -match [regex]::Escape((Join-Path $source $_)) })
} | ForEach-Object {
    $entryName = $_.FullName.Substring($source.Path.Length + 1)
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $_.FullName, $entryName)
}

$zip.Dispose()