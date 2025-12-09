# StoryScraper Agents

This document outlines a light-weight playbook for multiple agents (people or automations) who collaborate on StoryScraper. Each agent owns a distinct part of the pipeline so that a request such as “download this story from URL X” can be fulfilled consistently.

## 1. Intake Agent
- **Goal**: Collect requests (CLI invocations, tickets) and decide which download strategy applies.
- **Key actions**:
  - Parse CLI args (`uv run storyscraper ...`) and map `--name`/`--author` (slug) plus URL(s) into a story plan (respecting `--quiet`/`--verbose` preferences for downstream progress reporting).
  - When the user passes `--cookies-from-browser`, call the cookies loader to hydrate `storyscraper.http` so every downstream request reuses the extracted browser session.
  - use `src.storyscraper.urlclassifier` to determine if a site-specific strategy exists; otherwise fall back to the default downloader contract.
  - Pre-create the `stories/<slug>/` tree with `html/`, `markdown/`, `out/`, and `download_urls.txt`.

## 2. Fetch Agent
- **Goal**: Fetch raw HTML for each chapter URL.
- **Key actions**:
  - Step 1 (list-phase):
    - Use the fetcher selected by the Intake Agent, and load it from `src.storyscraper.fetchers`.
    - Create an url-file `stories/<slug>/download_urls.txt` with the final ordered list of URLs will be actually fetched.
    - URLs qualify for that list if they are in the same site domain and subdirectory as the options.download_url,
      i.e. if the download_url was https://mcstories.com/SilverLeash/index.html, we will load that page and extract chapter URLs https://mcstories.com/SilverLeash/.* from it
      and write that to the download_urls.txt file.
  - Step 2 (fetch-phase):
    - Read the `stories/<slug>/download_urls.txt` file.
    - Fetch each URL using the selected fetcher (pass `--force-fetch` to override existing HTML files).
    - Write the fetched HTML to `stories/<slug>/html/<slug>-<chapter_number:d>.html`.
    - Log any failures to `stories/<slug>/fetch.log`.

## 3. Transform Agent
- **Goal**: Convert HTML to Markdown.
- **Key actions**:
  - Use the transformer from `src.storyscraper.transformers` (default `auto`), which heuristically picks a content root (preferring `<main>`, `role="main"`, `<article>` or the deepest heading-containing subtree after stripping nav/header/footer) before converting it with markdownify (site-specific transformers like `mcstories_transformer` can tweak headings/milestones/etc.).
  - Emit Markdown files in `stories/<slug>/markdown/<slug>-<chapter_number:d>.md`, mirroring the fetch order.
  - Log conversion issues to `stories/<slug>/transform.log` so failures can be retried or escalated.

## 4. Packaging Agent
- **Goal**: Produce reader-friendly bundles (EPUB, PDF, etc.).
- **Key actions**:
  - Reuse the `stories/<slug>/markdown/Makefile` to render outputs into `stories/<slug>/out/`.
  - Ensure `markdown/Makefile` tracks dependencies so that rerunning the pipeline only rebuilds changed outputs.

## 5. QA Agent
- **Goal**: Validate the completed story package.
- **Key actions**:
  - Run `uv run pytest` (once tests exist) plus any link or spell-checkers.
  - Confirm metadata (title, author) matches the CLI request.
  - Approve the story directory for archiving or flag issues back to the Intake Agent.

## Communication Protocol
1. **Handoff artifact**: Each agent writes its result into the canonical story directory so the next agent can start without recomputation.
2. **Logs**: Every agent logs under `stories/<slug>/out/` with a timestamped Markdown or text record containing command-line options and notable events.
3. **Idempotency**: Agents should be able to re-run safely; existing files are overwritten only when all prerequisites pass validation.
4. **Coding standard**: Every change set must end by running `uv run ruff format src tests`, preceded by `uv run ruff check --fix` and `uv run mypy src` / `uv run pytest` so the repo stays type-safe, linted, and formatted.
5. **Change log**: After finishing work, prepend a `## YYYY-MM-DD by <name>` section to `CHANGES.md`, include a one-line summary, and list affected files/locations as bullet items so the entry reads like a detailed commit message.

This playbook can be refined as the codebase grows, but it already enables parallel work between specialists while keeping the repository organized.

## Developer Workflow
- **Architecture guardrails**
  - Keep new site-specific agents in `src/storyscraper/<type>/<site>.py` packages so story-specific logic stays isolated (e.g., `src/storyscraper/fetchers/mcstories.py`).
  - Persist every intermediate artifact inside the story directory; avoid temporary folders outside `stories/` so runs remain reproducible.
- Prefer idempotent operations—rerunning a command should either overwrite the same outputs or skip work when nothing changed.
- Route every outbound HTTP(S) request through `storyscraper.http` (`request`, `get`, or `fetch_bytes`) so Firefox-on-macOS masking and jittered delays always apply, even for future agents.
- `user-provided-data/` holds temporary, user-supplied artifacts. Do not modify files there or assume they persist; copy whatever you need into fixtures or repo-owned structures if required.
- **Tooling & dependencies**
  - Add dependencies with `uv add <package>` and remove them with `uv remove <package>`.
  - Use `uv lock` to bring the `uv.lock` file up to date. Do not edit `uv.lock` manually, it's autogenerated.
  - Mandatory tooling order: `uv run ruff check --fix`, `uv run mypy src`, `uv run pytest`, then `uv run ruff format src tests`.
