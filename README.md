# Cursor Engine

Pick any image or GIF and make it your Windows cursor. Animated GIFs become animated cursors.

## Run from source
    pip install -r requirements.txt
    python cursor_engine.py

## Get the .exe
Push to GitHub, open the **Actions** tab, click the latest run, and download the `CursorEngine` artifact.

## How it works
`engine.py` converts frames to 32-bit alpha `.cur` data (or a `.ani` RIFF container for animations),
saves them to `%APPDATA%\CursorEngine\cursors`, and sets them under `HKCU\Control Panel\Cursors`.
Your original cursor settings are backed up the first time you apply, and "Reset" restores them.
