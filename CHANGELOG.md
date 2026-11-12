# Changelog

Bookvox is a fork of [audiblez](https://github.com/santinic/audiblez) by Claudio Santini and continues from its
v0.4.9. Versions before 0.5.0 are upstream's. The format follows [Keep a Changelog](https://keepachangelog.com/).

## Unreleased

### Fixed
- The eSpeak library comes from Misaki's bundled copy instead of fragile system-path globs;
  `ESPEAK_LIBRARY` overrides it, and a missing or unloadable library fails fast with a clear
  error that names the override (#11).

## 0.5.3 - 2026-11-03

First release published from GitHub Actions with PyPI Trusted Publishing (no API token).

### Fixed
- The m4b chapters use the book's own chapter titles from its table of contents, and fall back to
  `Chapter 1`, `Chapter 2`, ... (they used to be numbered from 0). Titles with `=`, `;`, `#`, `\` or newlines are escaped
  correctly in the ffmpeg metadata.
- Progress could go above 100% on short books, which made the GUI progress bar raise an assertion.
- The GUI no longer uses the deprecated `wx.EmptyImage`.

### Changed
- The tests run in a temporary folder, so they no longer leave files in the repository.
- CI: unit tests run on Linux and Windows; the Windows conversion jobs install ffmpeg and fail if no m4b is produced.

## 0.5.2 - 2026-10-19

### Fixed
- The source book was deleted if its extension was uppercase (`.EPUB`).
- m4b creation failed for file names containing an apostrophe.
- The GUI imported `core` as a bare module, which loaded it twice. Errors in the conversion thread are now shown in a
  dialog instead of being lost.
- Package metadata declares the MIT licence correctly.

## 0.5.1 - 2026-10-19 (yanked)

### Fixed
- A relative output folder (`-o out`) broke the ffmpeg concatenation step.
- m4b creation failed on ffmpeg builds without `libfdk_aac`; it now uses the built-in `aac` encoder.

## 0.5.0 - 2026-10-19 (yanked)

- Renamed the project, package and commands to **bookvox** (`bookvox`, `bookvox-ui`).
