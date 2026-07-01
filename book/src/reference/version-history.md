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
- v0.45: declarative `package.ins` manifests plus `inscription package check` and `inscription package test`.
- v0.46: `inscription package build` for package-aware static libraries, executables, interface JSON, C headers, LLVM IR, and save temps.
- v0.47: local `Depend on Name from path "...".` package dependencies with dependency-aware package check/test/build.
- v0.48: internal deterministic interpreter groundwork for pure scalar/enum/record/union phrase evaluation.
- v0.49: `comptime` scalar/enum phrase-call evaluation using the pure interpreter.
- v0.50: `build.ins` MVP with the restricted built-in `Build` API for named artifact steps.
- v0.51: build script package check/test steps, including dependency-inclusive tests.
- v0.52: build script group steps, deterministic group dependencies, and an optional default step.
- v0.53: build script mdBook documentation steps with optional package-local example checking.
- v0.54: package-aware `build.ins` defaults for artifact and documentation steps.
- v0.55: standard `Build.standard package workflow.` shortcuts for conventional package CI/release workflows.
- v0.56: package `init`/`new` commands that generate formatter-clean package, build, source, test, and optional book skeletons.
- v0.57: package-wide formatting with `inscription package format`, Build format steps, and standard workflow format checks.
- v0.58: package clean command and `Build.clean` steps for deterministic build artifact hygiene.
- v0.60: deterministic release `.tar.gz` archives, checksum manifests, and `Build.release archive package.` steps.
- v0.59: deterministic package release bundles and `Build.release package.` bundle steps.
