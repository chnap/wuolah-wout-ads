# wuolah-wout-ads

Remove detected ads from Wuolah PDFs on your computer. No browser upload, OCR, or AI call: your PDFs stay local and cleaning uses **zero AI tokens**.

## Install (no Python, pipx, or repo clone)

Download the file for your computer from **[the latest release](https://github.com/chnap/wuolah-wout-ads/releases/latest)**:

| Computer | Download |
| --- | --- |
| Windows 64-bit | `wuolah-wout-ads-windows-x86_64.exe` |
| macOS Intel | `wuolah-wout-ads-macos-x86_64` |
| macOS Apple Silicon (M1/M2/M3/M4) | `wuolah-wout-ads-macos-aarch64` |
| Linux 64-bit (x86_64) | `wuolah-wout-ads-linux-x86_64` |

The download is the app; there is no installer. On Windows, open PowerShell and run:

```powershell
& "$HOME\Downloads\wuolah-wout-ads-windows-x86_64.exe" "$HOME\Downloads\apuntes.pdf"
```

On macOS or Linux, open Terminal in the download folder, allow execution once, then run it:

```bash
chmod +x ./wuolah-wout-ads-*
./wuolah-wout-ads-* ~/Downloads/apuntes.pdf
```

The executable is self-contained. You can move it anywhere and reuse it. If you already use Python, `pipx install git+https://github.com/chnap/wuolah-wout-ads.git` remains available as an alternative.

## Clean your PDFs

### One PDF (replace the original)

```bash
wuolah-wout-ads ~/Downloads/apuntes.pdf --json
```

The original file is replaced with its cleaned version, keeping the same name and folder. The write is atomic: if processing fails, the original stays in place. PDFs not recognized as Wuolah are skipped. Use `-o` if you want to save a separate copy instead.

### A whole folder

```bash
wuolah-wout-ads ~/Downloads/Wuolah --json
```

Pass a folder to scan it and all subfolders. The tool replaces recognized Wuolah PDFs in place, keeps their names and folders, and skips other PDFs. It processes up to four files at once. To save copies to a separate folder instead, use:

```bash
wuolah-wout-ads ~/Downloads/Wuolah -o ~/Downloads/Wuolah-limpios --json
```

If a path contains spaces, put it in quotes. For example:

```bash
wuolah-wout-ads "$HOME/Downloads/Mis apuntes.pdf"
```

## Optional switches

| Add this | To do this |
| --- | --- |
| `--json` | Print a compact summary for scripts or an AI agent. |
| `--jobs 8` | Process up to eight PDFs at once instead of the default four. |
| `--force` | With `--output`, replace output files that already exist. |
| `--help` | Show all options. |

Example with a summary:

```bash
wuolah-wout-ads ~/Downloads/Wuolah --json
```

`removed_regions` counts the detected ad areas covered, `removed_pages` counts entire promotional pages removed, `skipped` includes non-Wuolah PDFs, and `errors` counts PDFs that could not be processed. A skipped or unchanged PDF is left alone. With `--output`, an existing destination is skipped unless you add `--force`.

## Use it from Claude Code, Codex, or OpenCode

Install the agent skill once, globally, with the [Skills CLI](https://skills.sh/docs/cli):

```bash
npx skills add chnap/wuolah-wout-ads --skill wuolah-wout-ads --global
```

Then ask your agent: “Clean the PDFs in `~/Downloads/Wuolah` and save them in `~/Downloads/Wuolah-limpios`.” Make the downloaded executable available on your PATH, or install the Python command with `pipx`; the skill tells the agent how to process PDFs without reading their contents into the prompt.

## What it detects

- Dedicated Wuolah promotional pages with explicit promo text.
- Tracked ad links routed through `track.wlh.es` to advertising destinations.
- The specific top-banner plus side-banner image layout found around some Wuolah index pages.
- Linked advertising copy in page footers and invisible Wuolah tracking hotspots.

The rules were refined against a real 59-page sample with explicit promotional content, the paired banner layout, and linked footer ads. Other graphical banners are not identified by appearance.

## Limits

The cleaner has no OCR or general computer vision. Ads without explicit promotional text, recognizable ad links, or the specific paired banner layout may be missed. It preserves scanned study pages, normal Wuolah links, logos, watermarks, QR codes, legal notices, and academic content. A result with zero detected regions does not prove a PDF has no ads.

## Development

To work on the source code, clone the repo and install it in editable mode:

```bash
git clone https://github.com/chnap/wuolah-wout-ads.git
cd wuolah-wout-ads
python -m pip install -e .
```

MIT licensed. See [LICENSE](LICENSE).
