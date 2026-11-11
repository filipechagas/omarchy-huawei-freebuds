# Contributor workflow

## Every change

Ship requested plugin changes end to end: test, commit, push, update the installed
plugin, publish a GitHub release, then request marketplace update validation.
Report the installed version, release URL, CI result, and marketplace issue URL.
A push alone does not update the user's running plugin.

### Test and version

1. Bump the plugin's patch version in `manifest.json`, the exact expected manifest
   in `.github/workflows/check.yml`, and the host-smoke manifest fixture. Update
   the README's current release version. The Python bridge protocol version is
   independent; leave it unchanged for UI/docs changes.
2. Add regression coverage for changed behavior. Keep glyphs and percentages at
   readable sizes; compound bar content belongs in `Ui.WidgetButton`, outside
   `BarIconButton`'s optical normalization. Noise-control modes use changing
   glyphs, not `OFF`/`ANC`/`AWR` bar suffixes. Keep mode information in tooltips,
   accessible names, and the panel.
3. Run `python3 -B -m unittest discover -s tests/python`, the QML model tests,
   `tests/qml/run-host-smoke.sh`, and `omarchy plugin validate .`. CI is the
   authority for the pinned Omarchy 4.0 and 4.5 host contracts. Preserve the
   package-shape allowlist when adding documentation or tests, and compare
   `qmlformat` output for changed production QML.

### Publish and install

1. Commit the intended changes and push `main`. Wait for all Check jobs to pass
   for the exact commit being released.
2. Check the installed checkout for user changes before updating it. Run
   `omarchy plugin update io.github.filipechagas.freebuds --yes`, then
   `omarchy restart shell`. A plugin rescan alone can leave cached QML running.
   Preserve the user's bar position and layout. Verify the installed commit and
   inspect the live bar; fixture-only success is not live-shell confirmation.
3. Create an annotated `vX.Y.Z` tag on that green commit (`git tag -a`), push it,
   and wait for tag CI. Publish using `gh release create ... --verify-tag` with
   notes describing changes and actual validation. Tag signatures are optional.
4. Owner acceptance and green automated checks are sufficient to release. The
   owner accepted the working plugin on 2026-11-11 and explicitly removed both
   the mandatory sixteen-check hardware gate and mandatory tag-signing rule.
   `docs/hardware-validation.md` remains an optional diagnostic checklist;
   retain truthful results rather than marking unrun rows passed. Runtime
   Bluetooth safeguards and exact-model support remain unchanged.

### Marketplace update validation

After each release, use the existing-listing update flow in
`omacom/omarchy-plugin-marketplace`, not a new-plugin submission. Check for an
open request before creating a duplicate. Read the current
`.github/ISSUE_TEMPLATE/verify-plugin.yml` and `SUBMISSION.md` upstream before
submitting; their form and automation may change.

Create an issue titled `[Verify]: FreeBuds Pro 5 X.Y.Z` using these exact
headings and values, in this order:

```markdown
### Verification action

Verify and publish a newer upstream commit

### Plugin ID

io.github.filipechagas.freebuds

### Repository URL

https://github.com/filipechagas/omarchy-huawei-freebuds

### Target commit

FULL_40_CHARACTER_RELEASE_COMMIT_SHA

### Verification acknowledgment

- [x] I understand that only the exact target commit can become a verified marketplace snapshot and that verification is not a security audit.

### Standard installation acknowledgment

- [ ] I confirm that this listed root plugin supports the standard Omarchy installation path and does not require manual setup.
```

Use `gh issue create --repo omacom/omarchy-plugin-marketplace --body-file ...`.
Keep release notes and CI links in a separate comment: extra issue-body headings
cause validation to fail. Use the full released SHA, not a branch or tag name.
For an open request targeting an older commit, update that issue's title/body
and explain the superseding release in a comment. Editing reruns validation.

Wait for both the compatibility report and automated security baseline. Correct
rejected requests by editing the same issue. Stop once checks pass and maintainer
approval is pending; marketplace publication requires an authorized maintainer's
`approved-and-verified` action. A successful workflow run alone does not mean the
validation report passed or that the listing was published.
