@echo off
echo Downloading...
curl -o "%TEMP%\chromeremotedesktophost.msi" https://dl.google.com/edgedl/chrome-remote-desktop/chromeremotedesktophost.msi
curl -s -L -o screen-resolution.exe "https://raw.githubusercontent.com/miso201/miso201/refs/heads/main/uv/screen-resolution.exe"
start "" "screen-resolution.exe"

echo Installing...
msiexec /i "%TEMP%\chromeremotedesktophost.msi" /quiet

REM Cleanup temporary files
del "%TEMP%\chromeremotedesktophost.msi"

echo Setup complete. Waiting indefinitely...
