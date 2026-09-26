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

The cleaned PDF is saved beside the original as `apuntes_clean.pdf`. You can move the executable anywhere and reuse it. If you already use Python, `pipx install git+https://github.com/chnap/wuolah-wout-ads.git` remains available as an alternative.

## Clean your PDFs

### One PDF

```bash
wuolah-wout-ads ~/Downloads/apuntes.pdf
```

Done. The cleaned copy appears beside the original as `apuntes_clean.pdf`.

### A whole folder

```bash
wuolah-wout-ads ~/Downloads/Wuolah -o ~/Downloads/Wuolah-limpios
```

It scans subfolders, keeps their folder structure, and processes up to four PDFs at once. Your originals stay where they are.

If a path contains spaces, put it in quotes. For example:

```bash
wuolah-wout-ads "$HOME/Downloads/Mis apuntes.pdf"
```

## Optional switches

| Add this | To do this |
| --- | --- |
| `--json` | Print a compact summary for scripts or an AI agent. |
| `--jobs 8` | Process up to eight PDFs at once instead of the default four. |
| `--force` | Replace output files that already exist. The input is never overwritten. |
| `--help` | Show all options. |

Example with a summary:

```bash
wuolah-wout-ads ~/Downloads/Wuolah -o ~/Downloads/Wuolah-limpios --json
```

`removed_regions` counts the detected ad areas covered, `removed_pages` counts entire promotional pages removed, and `errors` counts PDFs that could not be processed. If the output already exists, that file is skipped unless you add `--force`.

## Use it from Claude Code, Codex, or OpenCode

Install the agent skill once, globally, with the [Skills CLI](https://skills.sh/docs/cli):

```bash
npx skills add chnap/wuolah-wout-ads --skill wuolah-wout-ads --global
```

Then ask your agent: “Clean the PDFs in `~/Downloads/Wuolah` and save them in `~/Downloads/Wuolah-limpios`.” Install the Python command with `pipx` as shown above; the skill tells the agent how to run it without reading PDF contents into the prompt.

## What it detects

- Dedicated Wuolah promotional pages with explicit promo text.
- Tracked ad links routed through `track.wlh.es` to advertising destinations.
- Linked advertising copy in page footers and invisible Wuolah tracking hotspots.

The rules were refined against a real 59-page sample with explicit promotional content and linked footer ads. Detection is based on text and PDF link metadata; it does not identify arbitrary graphical banners by appearance.

## Limits

The cleaner has no OCR or computer vision. Ads without explicit promotional text or recognizable ad links may be missed. It preserves scanned study pages, normal Wuolah links, logos, watermarks, QR codes, legal notices, and academic content. A result with zero detected regions does not prove a PDF has no ads.

## Development

To work on the source code, clone the repo and install it in editable mode:

```bash
git clone https://github.com/chnap/wuolah-wout-ads.git
cd wuolah-wout-ads
python -m pip install -e .
```

MIT licensed. See [LICENSE](LICENSE).
