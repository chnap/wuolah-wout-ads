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

By default, the cleaner also removes detectable Wuolah branding: Wuolah links and metadata, page text that names Wuolah, its repeated Spanish rights footer (including the rotated side version), and small image marks repeated in the same footer position on most pages. It also removes an image-based first-page cover and sparse, near-full-page image inserts surrounded by text-heavy notes. These deterministic layout rules require no AI or OCR. The JSON reports removed pages and their reasons in `removed_page_reasons`, and marks in `removed_branding`. Use the `--keep-*` switches to retain these items.

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
| `--dry-run` | Report detections without writing files. Combine with `--json` to review the results. |
| `--assume-wuolah` | Process one PDF even if its metadata and links do not identify it as Wuolah. Not allowed on a folder. |
| `--keep-wuolah-branding` | Keep detectable Wuolah links, metadata, footer text, and repeated footer image marks. |
| `--keep-wuolah-cover` | Keep a first page that looks like a sparse, image-based cover. |
| `--keep-full-page-ads` | Keep sparse, near-full-page image pages between text-heavy pages. |
| `--branding-repeat-ratio 0.7` | Minimum share of pages where a small footer image must repeat to be treated as a Wuolah mark (default `0.70`). |
| `--branding-footer-top 0.82` | Minimum normalized vertical position for repeated footer marks (default `0.82`). |
| `--branding-max-width 0.4` / `--branding-max-height 0.08` | Maximum normalized dimensions for a repeated footer mark. |
| `--full-page-image-coverage 0.9` | Minimum share of a page covered by one image to consider cover or insert rules (default `0.90`). |
| `--wuolah-cover-max-text 500` | Maximum extracted text characters for the first-page cover rule. |
| `--full-page-ad-max-text 80` | Maximum extracted text characters for an interstitial full-page ad (default `80`). |
| `--full-page-neighbor-min-text 500` | Minimum extracted text characters in each neighboring page for an interstitial ad (default `500`). |
| `--min-link-area 0.002` | Lower the minimum ad-link rectangle size (fraction of page area; default `0.004`). |
| `--max-link-area 0.9` | Raise the maximum ad-link rectangle size (default `0.80`). Larger links may cover study scans, so use carefully. |
| `--banner-tolerance 0.04` | Allow a larger gap between the top and side banner (default `0.025`). |
| `--banner-top-min-width 0.80` | Detect narrower top strips (default `0.84`). |
| `--banner-side-min-height 0.65` | Detect shorter side strips (default `0.70`). |
| `--image-redaction pixels\|remove\|none` | Default `pixels` blanks only detected image pixels; `remove` removes an intersecting image object; `none` leaves images untouched. |
| `--graphics-redaction contained\|covered\|none` | Control vector graphics in ad zones (default `contained`). `covered` removes any intersecting vector graphic and may affect nearby content. |
| `--redaction-color '#FFFFFF'` | Set the fill color of cleared regions using a hex color. |
| `--help` | Show all options. |

Example with a summary:

```bash
wuolah-wout-ads ~/Downloads/Wuolah --json
```

`removed_regions` counts detected ad areas covered, `removed_pages` counts entire promotional pages removed, `removed_page_reasons` explains each page removal, and `removed_branding` counts detected Wuolah links, metadata fields, page text, the repeated rights footer, and repeated footer images. `skipped` includes non-Wuolah PDFs, and `errors` counts PDFs that could not be processed. A skipped or unchanged PDF is left alone. With `--output`, an existing destination is skipped unless you add `--force`.

The image-redaction default is `pixels`: it clears detected pixels inside an ad rectangle instead of leaving the underlying banner image visible. The detector still uses the recognized Wuolah patterns; tune its area and banner thresholds only when the JSON shows a specific miss.

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
- Wuolah named links and metadata, footer text, and small images repeated in a consistent footer position across most pages.
- The repeated Spanish rights statement added along the bottom or rotated along the right edge of pages.
- A sparse, image-based cover on page one and sparse, near-full-page image inserts between text-heavy study pages.

The rules were refined against a real 59-page sample with explicit promotional content, the paired banner layout, linked footer ads, and a repeated footer image mark. Redaction blanks pixels within detected ad boxes so banner images do not remain visible under a text-only overlay.

## Limits

The cleaner uses deterministic Python rules, with no OCR, computer-vision model, or AI call. It clears the repeated rights footer by removing its detected text rectangles; it does not crop or reflow the author's page layout, so whitespace that belongs to the source remains. A full-page insert is removed only when it has very little extractable text, covers most of the page with an image, and sits between text-heavy pages; scanned study pages can still resemble this pattern, so tune the thresholds or use `--keep-full-page-ads` if needed. Other visual marks may remain when they cannot be attributed safely to Wuolah. A downloaded PDF cannot be reconstructed exactly as the author originally exported or sent it. A result with zero detections does not prove a PDF has no ads or platform marks.

## Development

To work on the source code, clone the repo and install it in editable mode:

```bash
git clone https://github.com/chnap/wuolah-wout-ads.git
cd wuolah-wout-ads
python -m pip install -e .
```

MIT licensed. See [LICENSE](LICENSE).
