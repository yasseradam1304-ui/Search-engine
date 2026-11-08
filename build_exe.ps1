$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
    $arguments = @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", "Adogle",
        "--add-data", "$PSScriptRoot\QT File.ui;.",
        "--distpath", "dist",
        "--workpath", "build",
        "--specpath", "build",
        "$PSScriptRoot\Python code.py"
    )

    python @arguments
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
