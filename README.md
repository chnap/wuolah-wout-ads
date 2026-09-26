# wuolah-wout-ads

Remove detected ads from Wuolah PDFs on your computer. No browser upload, OCR, or AI call: your PDFs stay local and cleaning uses **zero AI tokens**.

## Install once (no repo folder)

If you have [pipx](https://pipx.pypa.io/latest/how-to/install-pipx/) installed, run:

```bash
pipx install git+https://github.com/chnap/wuolah-wout-ads.git
```

This installs the `wuolah-wout-ads` command in pipx's isolated app environment. You do not need to clone the repo into your Downloads folder or beside your PDFs.

To run it once without keeping the app installed:

```bash
pipx run --spec git+https://github.com/chnap/wuolah-wout-ads.git wuolah-wout-ads ~/Downloads/apuntes.pdf
```

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
- The paired top and side banner layout found around a Wuolah index page.
- Linked advertising copy in page footers and invisible Wuolah tracking hotspots.

The rules were refined against a real 59-page sample with a cover banner, two index banners, and linked footer ads. It detected 76 ad regions while keeping the study pages and legal notices.

## Limits

The cleaner has no OCR or computer vision. Unlinked image ads outside the recognized banner layout may be missed. It preserves scanned study pages, normal Wuolah links, logos, watermarks, QR codes, legal notices, and academic content. A result with zero detected regions does not prove a PDF has no ads.

## Development

To work on the source code, clone the repo and install it in editable mode:

```bash
git clone https://github.com/chnap/wuolah-wout-ads.git
cd wuolah-wout-ads
python -m pip install -e .
```

MIT licensed. See [LICENSE](LICENSE).
