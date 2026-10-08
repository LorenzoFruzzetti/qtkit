# Guide: Turning a Research Analysis Project into a Reusable, Publishable Package

This guide is **project-agnostic**. Drop it into the root of any scientific
analysis repository (imaging, electrophysiology, omics, behaviour, and so on)
and give it to a human or an AI agent. It explains how to:

1. Find the code that can be reused, starting from the pipeline the project actually runs.
2. Separate that code from everything tied to one experimental design, which stays private.
3. Prepare the reusable part for public release (for example on GitHub) without changing scientific results.
4. Produce `REFERENCE.md`, a detailed usage reference that lets an agent or a new user run *new* analyses with the package ([§6.5](#65-referencemd-usage-reference-for-running-new-analyses-agent-oriented)).

It contains no information about any specific project. Every project-specific
fact must be found by reading the target repository. Write those facts into a
separate, private state document (see [§10](#10-required-deliverables)).

> If the repository also has an agent contract (for example `CLAUDE.md`,
> `AGENTS.md` or `CONTRIBUTING.md`), follow it for environment management,
> coding style and validation commands. This guide adds the
> *public/private split*. It does not replace those rules.

---

## 0. Vocabulary (map these onto the target domain first)

Before starting, write a short table that translates these generic terms into
the target project's terms. The rest of the guide uses only the generic terms.

| Generic term | Meaning | Imaging example | Electrophysiology example | Omics example |
|---|---|---|---|---|
| **Acquisition file** | Raw file produced by an instrument | `.lif`, `.czi`, `.nd2`, `.tif` stack | `.abf`, `.nwb`, `.rhd`, `.smrx` | `.fastq`, `.raw`, `.mzML` |
| **Recording** | One acquisition unit inside a file | image series / z-stack | sweep / trial / session | sample / run |
| **Channel** | Parallel signal inside a recording | fluorescence channel | electrode / ADC channel | lane / barcode |
| **Unit of analysis** | Object every metric is computed for | cell, nucleus, ROI | spike-sorted unit, event, sweep | gene, peptide, cell |
| **Detection / annotation** | How units are located | blob detection, manual ROI | spike detection, event markers | alignment, peak calling |
| **Metric** | Number computed per unit | intensity, texture, shape | firing rate, AP half-width | expression, abundance |
| **Condition / group** | Experimental factor | treatment, genotype | drug, stimulus protocol | treatment, timepoint |
| **Replicate / block** | Independent repeat | culture, slide, animal | animal, slice, cell | biological replicate |

---

## 1. Inputs to collect before touching anything

- **Primary entrypoint.** Which script does the user actually run end to end? Trace from that script. Do not start from the package folder. Old code often sits unused next to the live pipeline.
- **Downstream steps.** What happens after the primary run: aggregation, metadata joining, statistics, figures?
- **Which outputs are the result of record.** Which files or figures went into a paper, report or thesis? Those outputs must be reproducible after the refactor.
- **Publication scope.** What may be public (algorithms, generic readers, metric definitions)? What must stay private (sample names, condition labels, unpublished hypotheses, collaborator names, data paths, raw data)?
- **Environment.** Which environment manager the project uses, and whether the agent may create or modify environments.
- **Destructive operations.** Whether files may be moved or deleted, and whether the user must confirm each move.

Record the answers at the top of the private state document.

---

## 2. Phase A: Inventory (read-only)

**Goal:** a complete, factual picture of what runs today. Do not edit code in this phase.

### 2.1 Trace the live call graph
- Start at the primary entrypoint and follow every call into project modules. Note the file, the function and its line range.
- For every function on the path, record:
  - its inputs and outputs (types, array shapes, units),
  - its side effects (files written, figures saved, prints, global state),
  - the parameters that change behaviour, and where their values come from (argument, constant, config, hard-coded literal).
- Mark functions that are **defined but never reached** from any entrypoint. They are candidates for archiving, not for publishing.

### 2.2 Map the data flow
- Draw the chain: acquisition file → loaded arrays → detected units → per-unit metrics → per-recording table → aggregated table → metadata join → statistics → figures.
- For each intermediate file, write down its **schema**: file name pattern, column names, units, index meaning, and coordinate conventions (for example row/column vs x/y, 0- or 1-based indexing, sample vs millisecond).
- Note where **metadata** (condition, replicate) enters the pipeline: file names, folder names, a mapping table, or literals in code.

### 2.3 Classify every file and function
Give every item on the live path **exactly one** of these labels:

| Label | Definition | Destination |
|---|---|---|
| **CORE** | Pure computation on arrays or tables. Knows nothing about this experiment. | Public package |
| **IO-ADAPTER** | Reads or writes a generic file format or schema. | Public package (`io/`) |
| **ORCHESTRATION** | Chains CORE and IO steps and loops over files. Generic once its parameters come from config. | Public package (`pipeline.py`) |
| **VIZ** | Generic plotting or QC figures. | Public package (optional extra) |
| **STATS** | Generic statistical tests on a tidy table. | Public package (`stats/`) |
| **EXPERIMENT** | Encodes this study: paths, condition names, channel assignments, file-name parsing, thresholds tuned for this dataset, inclusion/exclusion rules, colour maps for named groups. | Private layer |
| **EXPLORATION** | One-off investigation, alternative metric attempts, notebooks. | `debugging_scripts/` (private) |
| **DEAD** | Never reached, commented out, or superseded. | Archive after confirmation |

A single function often mixes labels. In that case **split it** (see §4.3). Never publish it as it is.

### 2.4 Signs that code is tied to the experiment
Search for these. Each hit is either EXPERIMENT code or a parameter that must move into config:

- absolute paths, drive letters, user home directories, network shares;
- lists of fallback directories to search;
- literal sample, condition, gene, construct, protocol or animal names;
- string checks on file or folder names (`"X" in name`, regex on names) that **infer metadata**;
- hard-coded channel or electrode indices, or remapping by channel count;
- magic numbers tuned on this data: size cutoffs, thresholds, window lengths, bin counts;
- values that override a function argument (`num_workers = 1` written after reading config);
- fixed colour or label dictionaries keyed by group names;
- output folder names that encode a date or analysis version;
- fixed debug side effects (`savefig("p.png")`, pickles written to the working directory);
- a module-level script body (code that runs on import).

Useful commands (adapt the patterns):

```bash
# Absolute paths and drive letters
grep -rnE '([A-Za-z]:[\\/])|(/home/|/Users/|/mnt/)' --include=*.py .
# Literal names that look like metadata (fill in names found during inventory)
grep -rnE '"(ctrl|control|wt|ko|treat)[^"]*"' --include=*.py .
# Debug artefacts and import-time side effects
grep -rnE "savefig\(['\"][^/'\"]+\.png|pickle\.dump|^[a-z_]+\s*=.*read_csv" --include=*.py .
```

### 2.5 Record known defects and do not fix them yet
List every bug, inconsistency or documentation drift you find: unreachable branches, undefined variables on some paths, dependencies missing from requirements, docs that describe a different tool, two definitions of one metric. **Do not fix them during the move** (see §7). Fix each one later in its own change, with a before/after comparison.

---

## 3. Phase B: Target architecture

### 3.1 Two layers, one dependency direction

```text
public package  <──depends on──  private experiment layer
(generic, published)             (paths, conditions, tuned parameters,
                                  metadata, project scripts, results)
```

- The public package must **never import** from the private layer.
- The private layer contains no algorithms. It contains configuration, metadata tables and thin scripts that call the package.

### 3.2 Recommended repository layout

```text
<public_repo>/                      # published, e.g. on GitHub
├── pyproject.toml                  # package metadata, dependencies, optional extras
├── README.md                       # install, quick start, I/O contracts, examples
├── REFERENCE.md                    # complete usage reference for new analyses, agent-oriented (§6.5)
├── scripts/build_reference.py      # regenerates the AUTO sections of REFERENCE.md from the code
├── LICENSE
├── CITATION.cff                    # how to cite (methods packages are cited)
├── CHANGELOG.md
├── .gitignore
├── src/qtkit/                      # optional: reusable GUI kit, copied unchanged when a GUI is needed
├── src/<package_name>/
│   ├── __init__.py                 # small, explicit public API
│   ├── config.py                   # typed config dataclasses with documented defaults
│   ├── io/                         # readers/writers for acquisition files and intermediate schemas
│   ├── detection/                  # locating units (automatic or from annotations)
│   ├── metrics/                    # per-unit computations, one family per module
│   ├── pipeline.py                 # orchestration: file -> recordings -> units -> table
│   ├── aggregate.py                # combine per-recording tables, join metadata table
│   ├── stats/                      # generic tests on a tidy table
│   ├── viz/                        # optional plotting / QC, never called by core
│   ├── gui/                        # optional desktop GUI built on src/qtkit (GUI_DESIGN_GUIDELINES.md)
│   └── cli.py                      # `python -m <package_name> --config cfg.yaml`
├── tests/
│   ├── data/                       # tiny synthetic fixtures only
│   ├── test_metrics_*.py           # unit tests on synthetic arrays with known answers
│   └── test_pipeline_smoke.py
├── examples/
│   ├── README.md
│   ├── config_example.yaml
│   ├── metadata_example.csv
│   └── run_example.py              # runs on synthetic data, finishes in seconds
└── docs/                           # optional: method descriptions, schema reference

<private_project>/                  # never published (separate repo, or git-ignored folder)
├── configs/                        # one YAML/TOML per analysis run
├── metadata/                       # file/folder -> condition, replicate tables
├── scripts/                        # thin editor-runnable entrypoints (RUN_CONFIG pattern)
├── analysis/                       # study-specific stats/figure scripts
├── debugging_scripts/
├── data/  outputs/                 # git-ignored
└── PROJECT_STATE.md                # private state document (§10)
```

### 3.3 Design decisions for the layout
- **Use a `src/` layout.** Tests then run against the installed package, not against files that happen to sit in the working directory. This catches missing modules and packaging mistakes before users hit them.
- **Keep the private layer in a separate repository, or at least a separate folder.** Do not keep it in a git-ignored folder inside the public repo. Committing `git add .` in the wrong place is the most common way private data leaks, and private files stay in git history even after deletion.
  - *Acceptable alternative, if the user wants the data in the same folder:* use an **allowlist** `.gitignore`. It ignores everything (`/*`) and then re-includes only the public folders (`!/src/`, `!/tests/`, ...). A blocklist that names data folders fails open: any new folder is committed by default. Before the first push, check the tracked files with `git status --ignored` and a size check.
- **Have the private layer consume the package with `pip install -e <path_to_public_repo>`.** Both layers then evolve together, and the private side exercises the public API like any external user would.
- **Split modules by responsibility (io, detection, metrics, stats, viz), not by experiment or date.** Users look for "the texture metric", not "the March analysis".
- **Install plotting and UI as optional extras** (`pip install pkg[viz]`). Headless users and compute clusters should not need GUI or plotting dependencies just to compute metrics.
- **Build any desktop GUI on the bundled kit.** Copy `src/qtkit/` unchanged and follow `GUI_DESIGN_GUIDELINES.md` and `src/qtkit/README.md`. The project GUI (`src/<package_name>/gui/`) then contains only its commands, parameter hints, pipeline-guide steps, controller and views. The core package never imports the GUI or qtkit.
- **Keep the public API small and explicit in `__init__.py`.** Everything not exported is internal and may change. That gives the package room to evolve after release.

---

## 4. Phase C: Separation rules (what moves where)

### 4.1 Configuration instead of literals
- **Move every EXPERIMENT literal into a typed config object** (`dataclass`) with documented defaults, loaded from YAML/TOML by the private layer. Reviewers can then see every analysis choice in one file, and readers can reproduce a figure from its config alone.
- **Defaults in the public package must be neutral or justified** (documented in the docstring or cited). If a default was tuned on one dataset, make it a required parameter instead, so new users choose it on purpose.
- **Pass config explicitly; do not read globals or environment variables inside CORE functions.** Pure functions are testable and parallelisable.
- **Keep the editor-run convenience** (a `RUN_CONFIG` dict at the top of private scripts that is passed to the same parser as the CLI). Researchers run scripts from the editor, and both paths must build the same config object.

### 4.2 Metadata as data, not code
- **Store condition and replicate assignment in a mapping table** (`metadata.csv` with columns such as `recording_id, condition, replicate, include`). Never infer it with string matching in code. Name parsing is brittle, silently assigns `unknown`, and puts sample names into published code.
- **The public `aggregate` step joins the metadata table and fails loudly on unmatched recordings.** A silent left-join that drops rows changes the results without any warning.
- **Inclusion/exclusion rules belong in the metadata table (`include` column) or the private config.** They are study decisions and must be visible and reviewable, not buried in an analysis script.

### 4.3 Splitting mixed functions
Most research functions mix computation, plotting and file output. Split them like this:

```text
compute_<metric>(arrays, params) -> dict | DataFrame     # CORE: pure, no I/O, no plots
plot_<metric>_qc(arrays, result, params) -> Figure       # VIZ: returns a figure, does not save
save_<thing>(obj, path)                                  # IO: the only place files are written
```

- **CORE functions return values. Only the orchestrator decides what is written and where.** Writing files inside metric functions makes them slow, impossible to test without a disk, and dangerous in parallel runs.
- **A debug figure is opt-in through a flag and an explicit output directory.** It never writes to a fixed file name in the working directory.
- **One metric has one implementation.** If a composite metric is computed in two places (for example in the pipeline and again in a statistics script), keep one canonical function and have both callers use it. Two copies drift, and a column name can end up holding a different quantity than the methods text describes.
- **Column names describe what is stored.** If a column called `X` actually holds a different quantity, fix the name in the schema, add a `CHANGELOG` entry, and keep a compatibility alias for one release.

### 4.4 I/O contracts
- **Document every intermediate file in the README and in `io/` docstrings:** name pattern, columns, dtypes, units and coordinate conventions. External users plug their own detectors or annotation tools in at these boundaries.
- **Write a schema version or package version into output metadata** (a sidecar JSON or a header row). Results can then be traced to the code that produced them.
- **Do not delete or overwrite user files unless the user explicitly asks** (for example an `--overwrite` flag). Pipelines that clean their output folder can destroy annotations stored there.
- **Separate the input annotations folder from the output folder.** Mixing them is how pre-written inputs get overwritten by results.

### 4.5 What must never be published
- Raw or processed data, unless a data-sharing decision has been made. Use a data repository (Zenodo, DANDI, BioImage Archive, PRIDE, GEO, ...) and link to it.
- Absolute paths, machine names, user names, collaborator or patient identifiers.
- Sample, construct or condition names from unpublished work, including names in comments, docstrings, test fixtures and example file names.
- Notes, documents and figures about unpublished results.
- Environment folders, caches (`__pycache__`, `.ipynb_checkpoints`), pickles, editor settings with local paths.
- Git history that contains any of the above. **Publish from a fresh repository** with only the cleaned files. Do not rewrite the history of the working repository.

**Option: publishing the old code.** Some users want the original scripts
public for transparency (for example "the exact code behind the paper").
Treat them as follows:
- **Put them in a top-level `legacy/` folder that the package never imports,** with a `legacy/README.md` that says the code is unmaintained and points to the package. *Reason:* readers can audit the original analysis without mistaking it for the supported API.
- **Always replace absolute paths with placeholders** (`<DATA_DIR>`). *Reason:* paths reveal machines and users and do not work for anyone else anyway.
- **Ask the user explicitly whether the sample, condition and construct names in the legacy code may become public.** If not, replace them with neutral labels consistently and keep the mapping in the private layer. *Reason:* legacy code usually carries the most study-specific detail, so publishing it is a separate scope decision.
- **The leak audit (§6.3) then runs in two scopes:** strict for the package, tests, examples and README; paths-only (or paths + names, per the user's decision) for `legacy/`.
- **Under this option, "private" means data only:** raw and processed data, metadata tables, configs with real paths, and unpublished documents.

---

## 5. Phase D: Behaviour-preserving migration (step by step)

1. **Freeze a baseline.** Pick a small but representative subset of inputs (1–3 acquisition files, including an edge case). Run the current pipeline and store the outputs as **golden files** in the private layer.
   - *Why:* a refactor is only safe if "nothing changed" can be checked. Results computed for a manuscript must stay identical.
2. **Write a regression test** that reruns the subset and compares it to the golden files (exact for integers and strings, `rtol`-based for floats, same row order or a sorted comparison).
3. **Create the package skeleton** (`pyproject.toml`, `src/<pkg>/`, empty modules) and install it in editable mode in the project environment.
4. **Move CORE functions first.** Move them unchanged, update imports, and run the regression test.
   - *Why:* pure functions are the easiest to move and give the biggest reuse gain.
5. **Extract config.** Replace literals with config fields one function at a time. Set the private config to the old literal values. Run the regression test.
6. **Split mixed functions** (§4.3) one at a time. Run the regression test after each split.
7. **Move IO adapters and orchestration.** Replace hard-coded loops over folders with "list of inputs from config". Run the regression test.
8. **Replace metadata inference with the mapping table.** Generate the initial table from the current inference logic once, then review it by hand. Run the regression test.
9. **Rewire the private entrypoints** as thin scripts: load config, call the package, write outputs. Run the regression test.
10. **Archive** EXPLORATION and DEAD code into `debugging_scripts/` or an archive folder, after the user confirms.
11. **Fix known defects** (§2.5) only now, one per change. Record each output difference in the `CHANGELOG` and regenerate the golden files on purpose.
12. **Prepare the public repo** (§6) and run the leak audit (§6.3).

Rules for every step:
- **Make small batches, each ending green.** Bisecting a broken refactor across one large change costs much more time than small commits.
- **Moving code and changing behaviour are separate commits.** Reviewers can then confirm that a move is only a move.
- **Do not add `try/except` that hides errors** in scientific code. A crash is better than a silently missing row. (If a project-level contract says otherwise, follow it.)

---

## 6. Phase E: Publication readiness

### 6.1 Package hygiene
- `pyproject.toml` with name, version, Python version range, dependencies with lower bounds, and optional extras (`viz`, `gui`, `stats`, `dev`).
- **Every imported third-party module is declared.** Check by installing into a fresh environment and running the tests.
- **Code formatter and linter configuration** (for example `ruff`). Contributors then follow the same style without discussion.
- **Type hints on the public API** at minimum. They document array shapes and units, which matter most in scientific code.
- **Version `0.x` until the API settles,** with semantic versioning afterwards.

### 6.2 Documentation required in the public README
1. **What the package does**, in two sentences, with the scientific domain stated generically.
2. **Installation** (pip/conda), copy-paste ready.
3. **Quick start** that runs on the bundled synthetic example in under a minute.
4. **Entrypoints:** CLI command, Python API example, and how to run from an editor.
5. **Expected input:** supported acquisition formats, annotation schema, config fields.
6. **Expected output:** every file written, with its schema.
7. **Method description** for each metric: formula, parameters, assumptions and limitations. If a paper exists, link it.
8. **Directory map.**
9. **How to cite** (`CITATION.cff`) and the license.

### 6.3 Leak audit (must pass before the first push)
- Run the §2.4 grep patterns on the public tree; expected result: **zero hits**.
- Search for every sample, condition and person name listed in the private state document; expected result: **zero hits**.
- Check that no file in the public tree exceeds a size threshold (for example 1 MB) except deliberate fixtures.
- Check that `git log` of the public repo starts from the cleaned snapshot.
- Ask a second person (or a fresh agent session without the private context) to read the public repo. They should not be able to infer the unpublished study.

### 6.4 Choosing a license
- **Recommend a permissive license (MIT or BSD-3-Clause)** for analysis libraries, unless the user's institution requires something else. Permissive licenses maximise reuse in academia and industry. The user and their institution make the final decision; the agent only proposes.

### 6.5 `REFERENCE.md`: usage reference for running new analyses (agent-oriented)

The README tells a person what the package is and how to start.
`REFERENCE.md` does a different job: it is the **complete working manual for
using the package to run new analyses**. Write it so that an AI agent (or a new
lab member) with **no access to the original project and no prior
conversation** can plan and run an analysis on new data using this one file plus
the code.

#### 6.5.1 Design decisions
- **A separate file at the repo root, published, and shipped with the package** (include it in the sdist via `pyproject.toml`). *Reason:* the README stays short for humans; agents get one predictable file to load first, and it is next to the code they will call.
- **The reader is an agent with no context.** Nothing is implied. Every term is defined once, every path is relative to the repo root, every command can be copied and pasted. *Reason:* agents act on what is written. Gaps get filled with guesses, and guessed parameters produce plausible but wrong analyses.
- **Hybrid authorship: hand-written narrative + generated API sections.** Function signatures, docstrings and config fields are extracted from the code by a script (`scripts/build_reference.py`) between marker comments (`<!-- BEGIN AUTO:api -->` … `<!-- END AUTO:api -->`). Concepts, recipes and rules are written by hand. *Reason:* generated parts cannot drift from the code; hand-written parts carry the reasoning no docstring holds.
- **Drift check in the tests.** One test regenerates the AUTO blocks and fails if the committed file differs. *Reason:* a stale reference is worse than none, because agents trust it.
- **Every code block in `REFERENCE.md` is executed by the test suite** (extract the ` ```python ` blocks and run them on the bundled synthetic data). *Reason:* examples are what agents copy; a broken example becomes a broken analysis.
- **Task-oriented recipes, not only an API list.** *Reason:* agents start from a goal ("compute metric X per condition on new files"), not from a function name.
- **Explicit boundaries: what the package does NOT do and what must not be changed.** *Reason:* without them, agents "fix" core code to suit one dataset, which breaks reproducibility for everyone else.
- **Stable headings and fixed section order.** *Reason:* agents and humans can link to sections (`REFERENCE.md#config-reference`), and the generator can find its blocks.
- **Tables for parameters, columns and metrics; prose only for reasoning.** *Reason:* tables are scanned and parsed reliably by both people and agents.
- **Stamped with the package version and generation date.** *Reason:* the reader can tell whether the reference matches the installed version.
- **No study-specific content.** It passes the same leak audit as the package (§6.3). *Reason:* it is public.

#### 6.5.2 Required sections (in this order)

| # | Section | Content |
|---|---|---|
| 1 | **Header** | Package name, version, generation date, one-paragraph purpose, link to README |
| 2 | **When to use / when not to use** | Data types and questions the package fits; known non-fits, with pointers to better tools |
| 3 | **Agent operating rules** | See §6.5.3. Placed early so they are read before any action |
| 4 | **Setup and verification** | Install commands; one command that proves the install works (runs the synthetic example and prints the expected summary) |
| 5 | **Mental model** | Data-flow diagram (acquisition file → recordings → units → per-unit metrics → table → aggregate → stats); glossary of the domain terms used in identifiers |
| 6 | **Data contracts** | Supported input formats; annotation/detection schema; every intermediate and output file with name pattern, columns, dtypes, units, coordinate conventions, index base; example rows |
| 7 | **Config reference** *(AUTO + notes)* | Every config field: type, default, unit, valid range, the stage that reads it, effect of raising/lowering it, which fields have no safe default and must be set |
| 8 | **Public API** *(AUTO)* | For each exported symbol: import path, signature, parameters (with shapes and units), returns, raises, side effects (pure / writes files / plots), minimal example |
| 9 | **Metrics catalogue** | For each metric: output column, formula, inputs, range, direction ("higher means …"), assumptions, known sensitivities (noise, size, saturation), canonical function |
| 10 | **Recipes** | Complete runnable walkthroughs, at minimum: run the full pipeline on new files with a new config; compute one metric on in-memory arrays; use a different annotation/detection source; join a new metadata table and run the statistics; reproduce the bundled example result |
| 11 | **Extension points** | How to add a metric, a reader or a statistical test: files to create, function signature to follow, how to register it, tests required, which docs to update (including regenerating this file) |
| 12 | **Invariants and gotchas** | Axis order, index base, units, behaviours that look like bugs but are intentional (with the reason), outputs that are overwritten |
| 13 | **Errors** | Common error messages, their cause, and the fix |
| 14 | **Validation checklist for a new analysis** | What an agent must check before reporting results: config saved next to outputs, unit counts per group, no unmatched metadata rows, QC figures inspected, tests still passing |
| 15 | **Symbol index** *(AUTO)* | Alphabetical list: symbol → module path → one-line summary |

#### 6.5.3 Agent operating rules (copy into section 3 of `REFERENCE.md`, then adapt)
- Read `REFERENCE.md` fully before writing code. Look up every parameter here. Never invent a parameter or column name.
- Put study-specific choices (paths, thresholds, group names, exclusions) in a **config file and a metadata table** outside the package. Never edit package code for one dataset.
- To change or add a method, use an **extension point** (§11 of the reference), add tests with known answers, and regenerate `REFERENCE.md`.
- Use the documented entrypoints (CLI or the public API). Do not import private (`_`-prefixed) symbols.
- Do not wrap package calls in `try/except` to skip failing inputs. Fix the input or report the failure.
- Save the exact config and package version next to every output.
- Before reporting results, complete the validation checklist (§14 of the reference) and state any deviation.
- If something the analysis needs is not in the reference, stop and ask, or document the gap. Do not guess.

#### 6.5.4 How to generate it
1. Write the hand-written sections once the public API is stable (after §5 step 9).
2. Implement `scripts/build_reference.py`. It imports the package, walks `__all__`, and for each symbol uses `inspect.signature` and the docstring (numpy or Google style, consistently) to fill the AUTO blocks. Config fields come from the dataclass fields and their metadata (`field(metadata={"unit": ..., "doc": ...})`).
3. Add `tests/test_reference.py`:
   - (a) regenerate into a temporary file and compare it to the committed `REFERENCE.md`;
   - (b) extract and run every ` ```python ` block on the synthetic data.
4. Do a cold-start test: give only `REFERENCE.md` and the repository to a fresh agent session, with a new task (for example "compute the per-condition metric table for the example data with a different threshold"). Record every question it had to ask or every wrong assumption it made, then fix the reference. Repeat until the task completes without help.

---

## 7. Design decisions (summary checklist)

Use this list in reviews. Each item states the decision and the reason for it.

- **Trace from the entrypoint, not from the folder tree.** *Reason:* research repos keep obsolete modules next to live ones. Only code on the live path is known to produce the published results.
- **Public package and private experiment layer, with dependency in one direction only.** *Reason:* reusable and confidential code can then evolve and be shared independently, with no risk of the package needing private files.
- **Publish from a fresh repository.** *Reason:* deleted secrets stay in history, and history rewriting is error-prone.
- **Config objects instead of literals; required parameters instead of dataset-tuned defaults.** *Reason:* every analysis choice becomes explicit, reviewable and reproducible, and new users do not inherit thresholds tuned on someone else's data.
- **Metadata in tables, not in name parsing.** *Reason:* name parsing is brittle, leaks sample names into code and hides misassignments as `unknown`.
- **Pure CORE functions; I/O and plotting at the edges.** *Reason:* testability, safe parallelism and reuse in other pipelines (notebooks, GUIs, workflow managers).
- **One canonical implementation per metric, with column names that match the methods text.** *Reason:* duplicate implementations drift, and a mislabelled column leads to wrong scientific conclusions.
- **Golden-file regression tests before moving code.** *Reason:* the refactor must be provably neutral for results that are already reported.
- **Move first, fix later, in separate commits.** *Reason:* behaviour changes become visible, reviewable and attributable.
- **Errors surface; no defensive `try/except`.** *Reason:* in data analysis, a silent skip is a wrong result. Explicit input validation with clear error messages is preferred.
- **Synthetic example data with known answers.** *Reason:* tests and examples must run anywhere without sharing real data, and known answers prove the metric is computed correctly.
- **Optional extras for plotting and GUI.** *Reason:* keeps the core install light and server-friendly.
- **Editor-runnable private scripts (`RUN_CONFIG`) and CLI share one parser.** *Reason:* researchers run code from the editor; both paths must produce the same config.
- **Interactive tools (annotation GUIs, viewers) are separate packages or optional extras that talk to the core through the documented annotation schema.** *Reason:* GUI dependencies and platform issues should not block headless use, and the schema allows any annotation tool to be used.
- **Statistics consume a tidy table (`value, condition, replicate, ...`).** *Reason:* the same tests then work for any metric and any study design. Study-specific comparisons stay in the private layer.
- **Version and record provenance in outputs.** *Reason:* every result file can be traced to the code and config that produced it.
- **An agent-oriented `REFERENCE.md`, partly generated from the code, with executed examples and a drift test.** *Reason:* the package can then be reused for new analyses by people and agents without the original authors, and the reference cannot silently go out of date.

---

## 8. Domain adaptation notes

When applying this guide to a new domain, check these domain-specific points during Phase A:

- **Acquisition readers:** prefer established community readers (for example `bioio`/`aicsimageio`, `tifffile`, `readlif` for imaging; `neo`, `pynwb`, `pyabf` for electrophysiology; `pysam`, `pyopenms`, `anndata` for omics) over custom parsers. Wrap them in a thin `io/` adapter.
- **Units and sampling:** record pixel size, z-step, sampling rate and gain in config or read them from file metadata. Never assume them.
- **Coordinate and time conventions:** document axis order (`z, y, x` vs `x, y`) or (`channel, time`), and index base. Off-by-one and axis-swap bugs are the most common silent errors when users plug in their own data.
- **Units of analysis that nest** (unit within recording within replicate within condition): keep identifiers for every level in the output table. Statistics must then be able to treat the replicate, not the unit, as the independent observation when needed.
- **Community standards:** if one exists (NWB for electrophysiology, OME for imaging, AnnData for single-cell), support it as input or output. This raises reuse a lot.

---

## 9. Validation gates (all must pass)

- [ ] The regression test on the golden subset passes after the final migration step. Intentional differences are listed in the `CHANGELOG`.
- [ ] The package installs in a **fresh** environment from `pyproject.toml` alone, and the tests pass.
- [ ] `examples/run_example.py` runs on synthetic data from a clean clone.
- [ ] The private entrypoints run from the editor and from the terminal and produce the same outputs.
- [ ] The leak audit (§6.3) returns zero hits.
- [ ] The README covers every item in §6.2.
- [ ] `REFERENCE.md` has every section of §6.5.2; its drift test and executed-examples test pass; one cold-start agent run (§6.5.4 step 4) completed a new task without help.

---

## 10. Required deliverables

Whoever applies this guide produces:

1. **A private state document (`PROJECT_STATE.md`)** in the private layer, containing:
   - the answers to §1;
   - the vocabulary table from §0, filled in for this project;
   - the live call graph and data-flow chain (§2.1–2.2), with intermediate schemas;
   - the classification table (§2.3): file/function → label → destination;
   - the known defects list (§2.5);
   - the old → new path mapping;
   - the step plan (§5) with the status of each step;
   - the names and terms the leak audit must search for (§6.3).
2. **The public repository** that meets §3, §4 and §6, including **`REFERENCE.md`** and its generator (§6.5).
3. **The private layer** with configs, metadata tables, thin scripts and golden files.
4. **A final report** listing what changed, the validation results for each gate, risks, assumptions and open questions.

### Template for the classification table

| Item (file:function) | Label | Destination | Experiment-specific parameters to extract | Notes / defects |
|---|---|---|---|---|
| | | | | |

### Template for the old → new mapping

| Old path | New path | Layer (public/private/archive) | Step # | Confirmed by user |
|---|---|---|---|---|
| | | | | |
