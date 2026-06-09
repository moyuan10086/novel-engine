# Contributing

Thanks for taking a look at `novel-engine`.

## Development Setup

This project uses `uv`.

```bash
uv sync --all-extras
uv run --extra dev python -m pytest -q
```

## Pull Requests

Before opening a PR:

- keep changes focused
- run the test suite
- avoid committing private novel projects under `projects/`
- avoid committing `.env`, prompt previews, generated books, vector indexes, or platform-bound manuscript text
- update README/docs when behavior changes

## Code Style

The project currently keeps dependencies light and favors plain Python modules over framework-heavy abstractions.

When adding features:

- prefer existing CLI patterns
- keep generated manuscript text separate from engine code
- add tests for prompt assembly, state updates, and reader-facing cleanup
- avoid hard-coding one author's private worldbuilding into shared code

## Content Policy For Contributions

Do not submit copyrighted novels, leaked manuscripts, private prompts, or content you do not have rights to share.

Small synthetic fixtures are welcome. Real projects should stay local.
