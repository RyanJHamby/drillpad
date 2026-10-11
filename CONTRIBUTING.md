# Contributing

Thanks for helping. This project teaches by explaining mechanisms, so accuracy and honest sourcing matter more than volume.

## Hard rules for content

1. **No confidential or non-public material.** Do not submit anything covered by an NDA, anything from a non-public
   interview or employer, or private information about a person or company.
2. **No claims about a specific company's interview process or internal systems** unless you cite a public source
   (the company's own published guidance, a public engineering post, a paper). Label provenance as `documented`,
   `reported`, or `inferred`. Use generic domain wording ("a trading system", "an inference platform") instead of company
   names in examples and invented scenarios.
3. **No copied problem text.** Write problem statements in your own words and reference public lists by title.
4. **Invented numbers are labeled.** Use derived arithmetic from stated assumptions, cited figures, or numbers marked
   illustrative. Anything unverified gets a `[VERIFY]` tag.
5. **Code examples must run.** Say how you ran them.
6. **Disclose AI assistance** in the pull request description if a model drafted any part of it.

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
python scripts/course.py check        # course integrity and generated docs
```

Course changes are append-only: new lessons take the next number in their module, and existing lesson ids never change.
Use `python scripts/course.py new-lesson` or `new-module`, then `docs`. See `docs/MAINTAINING_THE_COURSE.md`.

## Licensing of contributions

By submitting a contribution you agree it is licensed under this project's licenses: MIT for code and CC BY 4.0 for
course content and documentation.
