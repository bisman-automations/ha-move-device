# Move Device: notes for Claude and other coding agents

Home Assistant custom integration (`move_device`), installed through the
Marketplace or HACS. It moves devices to another area from an admin-only
sidebar panel: the devices Home Assistant shows as linked move with them,
device names, entity names and entity IDs are renamed by swapping the area's
name (every suggestion can be edited), and the automations, scripts, scenes
and helpers that use the old entity IDs are listed with links to the editor,
for the person to update. Move Device never edits them. Read this before
changing anything.

## Layout

- `custom_components/move_device/`: the integration.
  - `__init__.py`: `async_setup` registers the websocket commands and the
    panel's static path once; the config entry (`single_config_entry`, no
    options) adds and removes the sidebar panel.
  - `names.py`: **pure (no Home Assistant imports)**: `swap_name`,
    `swap_object_id`, `slug`, `valid_entity_id`, `uses_entity_ids`. Whole words only, case ignored, longest phrase first.
  - `planner.py`: `async_preview` (changes nothing) and `async_apply`.
    Linked devices are those sharing an identifier or connection with a
    picked one (what **Linked devices** shows); read the device registry with
    `all_devices` (a mapping on 2026.8, iterable later; never `.values()`).
    The find words are the old area's name and aliases plus the panel's
    **Find**; the replacement is **Replace with** or the new area's name.
    Device names are written to `name_by_user`, entity names to the registry
    `name`; entities whose area was set to the device's old area follow it.
    `async_apply` checks every new entity ID (valid, same domain, unused)
    before changing anything, fires `move_device_moved`, and returns
    `needs_updating`: every reference to a renamed ID, found before the
    rename, each with `renames` (old -> new).
  - `references.py`: what uses the old IDs: core's `automations_with_entity`,
    `scripts_with_entity`, `scenes_with_entity`, plus each item of
    `automations.yaml`, `scripts.yaml` and `scenes.yaml` read as text (finds
    IDs in templates), plus every other config entry's data and options
    (helpers, listed only). Area targets come from `automations_with_area` /
    `scripts_with_area`. Read only: nothing here writes a file, reloads,
    or changes a config entry. `Reference.in_editor` marks the ones made
    in the editor (`/config/<kind>/edit/<item_id>`).
  - `websocket.py`: `move_device/preview` and `move_device/apply`, both
    `require_admin`.
  - `panel.py` + `frontend/move-device-panel.js`: the admin sidebar panel,
    one plain web component, no build step. It reads areas and devices from
    `hass.areas` / `hass.devices`; the server makes every suggestion.
- `tests/ha/`: pytest inside Home Assistant (`test_names.py` covers the pure
  rules). Tests point `hass.config.config_dir` at `tmp_path` so the UI-made
  files can be set up, and check a move leaves them byte for byte.

## Checks

The shared checks below. No mypy and no Node tests. For panel changes run
`node --check` on the script and look at it in a browser (Playwright is
available) with a fake `hass` at desktop and phone width (390px) and in the
dark theme.

## Conventions

- Nothing changes without the preview. Never edit, rewrite or reload an
  automation, script, scene or helper, and never write any YAML file: list
  them with editor links instead. A YAML rewrite (and its `update_references`
  option) was removed in 0.2.0 after the HACS review, hacs/default#14121;
  don't bring it back.
- Show names, not entity IDs, wherever the panel can; escape everything with
  `esc()`; use Home Assistant's theme variables.
- Entity unique IDs never change; only entity IDs, names and areas do.

## Open decisions

- None.

<!-- BEGIN bisman-automations shared rules -->
<!-- This block is the same in every bisman-automations repo. Edit it in
     bisman-automations/.github (templates/CLAUDE.shared.md) and copy it to
     every repo; the Validate workflow's "standards" job checks it matches. -->

## Shared rules (every bisman-automations repo)

### Releases

- The version lives in `custom_components/<domain>/manifest.json`. Anything
  else that repeats it is called out in the repo-specific notes below and is
  bumped in the same commit.
- Versions follow [Semantic Versioning](https://semver.org): patch for fixes,
  translations, docs and CI; minor for new features, options or entities;
  major when something users rely on is removed or renamed (entities,
  services, events, options) or setup has to be redone.
- Check what is released before choosing a version:
  `git ls-remote --tags origin | awk -F/ '{print $3}' | sort -V | tail -1`
  (`sort -V`: plain sorting puts `v1.10.0` before `v1.9.0`). Never add
  changes to a released version. If the manifest version has no tag yet,
  add to its CHANGELOG section instead of bumping again.
- Every push to `main` ships as a release. In that same commit, named
  `Release X.Y.Z`, bump the manifest version and write the notes directly
  under a new `## [X.Y.Z] - YYYY-MM-DD` heading in `CHANGELOG.md` (Keep a
  Changelog: Added, Changed, Deprecated, Removed, Fixed, Security), with
  that version's compare link at the bottom. There is no `## [Unreleased]`
  section and no `[Unreleased]:` compare link. New work is not collected
  under a holding heading and moved later; the release commit is where the
  heading and the entries are written. The standards check fails if a
  `## [Unreleased]` heading is present.
- Ask Donavan before every push. Push fast-forward only: never force-push,
  rebase or amend anything already pushed, or rewrite history in any other
  way. Rewriting history orphans the release tags (it broke drafting in
  ha-button-actions).
- Pushing to `main` runs **Draft release**, which creates or refreshes a
  draft `vX.Y.Z` with that version's CHANGELOG section as the notes, the
  commits since the last release and `<domain>.zip`. **Donavan publishes
  the draft himself**, and publishing creates the tag. Never create or push
  tags, publish releases, or edit published releases.
- Publishing runs **Release check**: the tag must match the manifest version
  and the CHANGELOG, and be on `main`. If it fails, fix it with a new patch
  release, not by moving the tag.

### Commits

- Author commits as `Donavan Becker <donavan.becker@icloud.com>` (set
  `git config user.name` / `user.email` in the clone). HACS's
  default-repository check needs the submitter to have a fair share of the
  commits. Credit an AI assistant with a `Co-Authored-By:` trailer if you
  like, never as the author.
- Subject lines are plain, imperative and say what changed for the user
  ("Show Pico remotes as unavailable when Lutron isn't running"). No
  `fix:`/`feat:` prefixes. Release commits are "Release X.Y.Z".
- Commit and push only when asked.

### CI (shared workflows)

- `.github/workflows/` holds four thin callers of the reusable workflows in
  [bisman-automations/.github](https://github.com/bisman-automations/.github):
  `test.yml` (lint, frontend, pytest on the oldest supported and the newest
  Home Assistant, plus the upcoming one as information only), `validate.yml`
  (hassfest, HACS, standards), `draft-release.yml` and `release-check.yml`.
  Don't add jobs to the callers. Use the shared workflow's inputs, or change
  the shared workflow so every repo gets the improvement.
- `requirements_test.txt` leaves `pytest-homeassistant-custom-component`
  unpinned (newest Home Assistant) and pins ruff (and mypy where used).
  `requirements_test_min.txt` pins the harness release for the minimum in
  `hacs.json`: the newest harness release of that month. CI fails if they
  drift apart.
- Raising the minimum Home Assistant means changing, together: `hacs.json`,
  `requirements_test_min.txt`, `python-min` in `test.yml` (3.13 up to
  2026.2, 3.14 from 2026.3), the README's Home Assistant badge, and a
  CHANGELOG entry.
- Home Assistant 2026.3 and newer need Python 3.14 (3.14.2+).
- The published hassfest rejects `categories` in `manifest.json` and Pillow
  in `requirements`. Leave both out.
- Dependabot (`.github/dependabot.yml`) proposes action and pinned-tool
  updates weekly. It ignores the test harness on purpose.
- Test and Validate also run every Thursday, the day after Home Assistant's
  betas come out. The **next** test job (newest pre-release harness) is
  information only: when it fails, fix the cause before that release ships.

### Before saying work is done

Run from the repo root, in a Python 3.14 venv with `requirements_test.txt`
installed:

```
ruff check .
ruff format --check .
pytest
```

Also run `node --test tests/*.mjs` when the repo has Node tests, mypy when
the repo-specific notes list it, and the tests in a second venv with
`requirements_test_min.txt` when a change could behave differently on the
oldest supported Home Assistant. The standards check (also in CI) is
`python <path to bisman-automations/.github>/scripts/check_repo.py .`.

### Code and docs

- Support every Home Assistant from the `hacs.json` minimum to the newest
  release. Check for deprecations in the newest release and the beta.
- Keep entity IDs, unique IDs, service names and event names stable. When
  one has to change, migrate it and say so under Changed in the CHANGELOG.
- `strings.json` and `translations/en.json` hold the same keys. Home
  Assistant reads only `translations/`, so change both in the same commit.
- Never put personal details in the repo (README, CHANGELOG, code, tests,
  screenshots): no names, addresses, account or device identifiers, or real
  entity IDs. Use placeholders such as `light.living_room`.
- `README.md` is user documentation with the standard header (badges, HACS
  and "add integration" My buttons) and sections Installation, Setup, ...,
  Troubleshooting, Development, License. Use plain language and show names,
  not entity IDs, wherever the UI does.
<!-- END bisman-automations shared rules -->
