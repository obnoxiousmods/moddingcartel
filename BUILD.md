# Building Windows Release

This document describes how to build `moddingcartel.exe` from the source code.

## Overview

The `send_to_switch.py` script is compiled into a single Windows executable called `moddingcartel.exe` using PyInstaller. When double-clicked, it opens a terminal window and runs the application.

## Prerequisites

- Python 3.10 or later
- pip (Python package installer)
- All dependencies from `requirements.txt`

## Building Locally

### Windows

1. Open Command Prompt or PowerShell in the project root directory
2. Run the build script:
   ```cmd
   build_windows.bat
   ```
3. The executable will be created in the `dist/` folder

### Linux/macOS

1. Open Terminal in the project root directory
2. Make the build script executable (first time only):
   ```bash
   chmod +x build.sh
   ```
3. Run the build script:
   ```bash
   ./build.sh
   ```
4. The executable will be created in the `dist/` folder

### Manual Build

If you prefer to build manually:

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. Install project dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run PyInstaller with the spec file:
   ```bash
   pyinstaller moddingcartel.spec
   ```

4. Find the executable in `dist/moddingcartel.exe` (Windows) or `dist/moddingcartel` (Linux/macOS)

## Automated Builds (GitHub Actions)

The repository includes a GitHub Actions workflow that automatically builds Windows releases:

- **Trigger**: Push a version tag (e.g., `v1.0.0`) or manually trigger the workflow
- **Output**: `moddingcartel.exe` uploaded as a release artifact
- **Location**: `.github/workflows/build-windows-release.yml`

### Creating a Release

1. Tag your commit with a version:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. GitHub Actions will automatically:
   - Build the Windows executable
   - Create a GitHub Release
   - Attach `moddingcartel.exe` to the release

### Manual Workflow Trigger

You can also trigger the build workflow manually from the GitHub Actions tab without creating a tag. The artifact will be available for download but won't create a release.

## Build Configuration

The build is configured in `moddingcartel.spec`:

- **Entry Point**: `software/send_to_switch.py`
- **Output Name**: `moddingcartel.exe` (Windows) or `moddingcartel` (Linux/macOS)
- **Mode**: Single-file executable (all dependencies bundled)
- **Console**: Enabled (terminal window opens when double-clicked)
- **Hidden Imports**: All required modules are explicitly listed
- **Excluded Packages**: Unused packages excluded to reduce file size

## Customization

### Changing the Icon

1. Create or obtain an `.ico` file (Windows) or `.icns` file (macOS)
2. Edit `moddingcartel.spec` and set the `icon` parameter:
   ```python
   exe = EXE(
       ...
       icon='path/to/your/icon.ico',
   )
   ```
3. Rebuild the executable

### Adding Data Files

If you need to bundle additional files (config templates, images, etc.):

1. Edit `moddingcartel.spec` and add to the `datas` list:
   ```python
   datas=[
       ('path/to/file.txt', '.'),  # File will be in root of bundle
       ('path/to/folder', 'folder'),  # Folder will be copied
   ],
   ```
2. Rebuild the executable

### Debugging Build Issues

If the build fails or the executable doesn't work:

1. Check the build logs for errors
2. Test with debug mode enabled:
   ```python
   exe = EXE(
       ...
       debug=True,
   )
   ```
3. Run the executable from command line to see error messages
4. Verify all hidden imports are listed in the spec file

## Distribution

The compiled `moddingcartel.exe` is a standalone executable that:

- Requires **no Python installation** on the target machine
- Bundles **all dependencies** internally
- Opens a **terminal window** when double-clicked
- Works on **Windows 10 and later**

Simply distribute the single `.exe` file to users. No installation required!

## File Size

The executable is typically 30-50 MB due to bundled Python runtime and dependencies. To reduce size:

1. Use UPX compression (enabled by default in the spec file)
2. Exclude unnecessary packages in the `excludes` list
3. Consider using `--strip` option for PyInstaller

## Security

The executable is not signed by default. For production releases:

1. Consider code signing the executable
2. Add virus scanning to your CI/CD pipeline
3. Provide checksums (SHA256) for downloads

## Troubleshooting

### "Python is not installed" error
- Ensure Python 3.10+ is installed and in your PATH

### "PyInstaller command not found"
- Run: `pip install pyinstaller`

### Build succeeds but executable crashes
- Check for missing hidden imports in the spec file
- Test with `debug=True` to see error messages
- Verify all dependencies are in `requirements.txt`

### Antivirus flags the executable
- This is common with PyInstaller executables
- Whitelist the file or submit to antivirus vendors
- Consider code signing for production releases
