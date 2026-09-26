# wuolah-wout-ads

Fast, local batch cleaner for advertising in Wuolah PDFs. It inspects PDF text, links, and image placement with PyMuPDF. Files stay on your machine: there is no OCR, upload, or AI call, so cleaning uses **zero AI tokens**.

## Quick start

Requires Python 3.10 or newer.

```bash
git clone https://github.com/chnap/wuolah-wout-ads.git
cd wuolah-wout-ads
python -m venv .venv
source .venv/bin/activate       # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install .
```

Clean one PDF:

```bash
wuolah-wout-ads "./downloads/lecture-notes.pdf" \
  --output "./clean/lecture-notes.pdf" \
  --json
```

Clean every PDF in a folder, including its subfolders:

```bash
wuolah-wout-ads "./downloads" \
  --output "./downloads-clean" \
  --jobs 4 \
  --json
```

The output folder keeps the input folder's relative structure. Use a separate output location so you can compare the cleaned copy with the original.

## Usage

```text
wuolah-wout-ads INPUT [-o OUTPUT] [-j JOBS] [--force] [--json]
```

| Option | Description |
| --- | --- |
| `INPUT` | A single PDF or a folder to scan recursively. The extension is case-insensitive. |
| `-o`, `--output` | Destination PDF for one input file, or destination folder for a folder input. |
| `-j`, `--jobs` | Number of PDFs to process at once. Defaults to up to 4. |
| `--force` | Replace existing output files. The input PDF is never overwritten. |
| `--json` | Print a machine-readable summary, useful for scripts and AI agents. |

If `--output` is omitted, a single `notes.pdf` becomes `notes_clean.pdf`; a folder called `notes` becomes a sibling folder called `notes_clean`. Existing outputs are skipped unless `--force` is used.

See all options with:

```bash
wuolah-wout-ads --help
```

## Reading the JSON result

The summary includes totals for files cleaned, promotional pages removed, advertising regions removed, and errors. Each file result includes its status, source and output paths, page count, removed page numbers, and removed regions.

```json
{
  "total": 1,
  "cleaned": 1,
  "removed_pages": 0,
  "removed_regions": 2,
  "errors": 0
}
```

`removed_regions` counts white redaction rectangles, not every hidden tracking link removed. A status of `skipped` means the output already existed or the input contained nothing but promotional pages; inspect its `error` field for the reason. A status of `error` means that file could not be processed.

## Using it with Claude Code, Codex, and OpenCode

The repository includes agent skills for Claude Code (`.claude/skills/`), Codex (`.agents/skills/`), and OpenCode (`.opencode/skills/`). Install the package in the same Python environment available to your agent, then ask it to clean a PDF or folder. The skill tells the agent to run one local batch command and summarize the JSON; it does not load PDF contents into the prompt.

Example request:

> Clean all Wuolah PDFs in `./downloads` and save the results in `./downloads-clean`.

## What it detects

- Dedicated promotional pages with explicit Wuolah promotional text.
- Ad click-through links routed through `track.wlh.es` to advertising destinations.
- Wuolah's edge-banner layout when a top banner and tall side banner appear together.
- Linked promotional copy in page footers. Invisible Wuolah tracking hotspots are removed too.

The rules were refined against a real 59-page sample with a cover banner, two edge banners around the index, and linked ads in page footers. On that sample, the tool detected 76 advertising regions while preserving the study pages, index, and legal notices.

## Limits

This version does not use OCR or computer vision. An unlinked image ad outside the recognized edge-banner layout may be missed. Scanned study pages are preserved, as are normal links to Wuolah, logos, watermarks, QR codes, legal notices, and academic content. A zero-region count means no current rule matched; it does not prove that a PDF has no advertising.

## Development

```bash
python -m pip install -e .
wuolah-wout-ads --help
```

MIT licensed. See [LICENSE](LICENSE).
