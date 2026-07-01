# Version History

The book tracks current Inscription, while historical sprint contracts remain in `docs/inscription-v*.md`.

Recent milestones:

- v0.23: nominal enums.
- v0.24: match expressions and match step blocks.
- v0.25-v0.26: tagged unions and multi-payload variants.
- v0.27: type aliases and storage aliases.
- v0.28: byte and byte-string literals.
- v0.29-v0.31: owned dynamic buffers, lexical cleanup, and owned-buffer returns.
- v0.32: prose-punctuation syntax.
- v0.33: canonical formatter.
- v0.34: explicit `then` parent-continuation clauses for nested punctuation control flow.
- v0.35: mdBook documentation site and GitHub Pages workflow.
- v0.36: explicit `move` and consuming owned-buffer parameters.
- v0.37: owned temporary moves with `move (call)` and consuming pipelines.
- v0.38: move-aware `When`/`Otherwise` and `Match` ownership merging for owned buffers.
- v0.39: exhaustive enum/union/bool matches and the `anything` wildcard pattern.
- v0.40: match arm guards with lowercase `when` and ignored union payload fields.
- v0.41: pattern alternatives with `or` and inclusive integer range patterns with `through`.
- v0.42: owned buffer `containing`, owned byte-string buffers, and explicit `owned buffer copied from source` initialization.
- v0.43: ordinary `//` comments, `///` declaration docs, `//!` module docs, interface JSON docs, and exported C header comments.
- v0.44: first-class `Test ... .` declarations, test-only `Expect ... .` assertions, and the `inscription test` runner.
