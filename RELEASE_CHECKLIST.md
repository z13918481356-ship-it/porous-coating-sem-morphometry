# Release checklist

Status recorded on 2026-08-30 for the standalone local repository on branch `codex/portfolio-release`.

## Completed locally

- [x] Project isolated from the unrelated parent `metal-oxide-thin-film-ml` repository.
- [x] Raw archives, extracted external images, partial downloads, dependency bundles, predictions, and model checkpoint excluded by `.gitignore`.
- [x] Candidate commit contains no file larger than 10 MB; total candidate size is approximately 12.5 MB.
- [x] No API keys, access tokens, passwords, private keys, personal filesystem paths, or embedded remote credentials found by repository text scan.
- [x] Three unit tests pass under Python 3.12.
- [x] All Python source and scripts compile.
- [x] README local links resolve.
- [x] `CITATION.cff`, MIT `LICENSE`, data card, model card, locked protocols, and reproducibility checklist are present.
- [x] `CITATION.cff` passes the CFF 1.2 schema validator.
- [x] Final DOCX accessibility audit reports zero findings.
- [x] Final PDF is two US Letter pages; every page has been rasterized and visually checked.
- [x] Report text contains the frozen U-Net/Otsu values and the eight-condition property-model limitation.
- [x] Public GitHub repository created at `z13918481356-ship-it/porous-coating-sem-morphometry` without auto-generated files.

## Public GitHub publication

- [x] Public repository name: `porous-coating-sem-morphometry`.
- [x] Public citation author inherited from the existing Git configuration: `Yuexuan Zhu`.
- [x] Empty GitHub repository created without another README, license, or `.gitignore`.
- [x] New repository URL added to `CITATION.cff` as `repository-code`.
- [x] Add the new remote and verify it does not point to the unrelated parent project.
- [x] Push `codex/portfolio-release`; GitHub Actions `tests` and the dependency-graph update both completed successfully before publishing the same reviewed commit to `main`.
- [x] Publish `v0.2.0` from commit `9c671b6953ca6107bb3135a333e0c1791c1cbbf3` and attach the final DOCX/PDF reports.
- [x] Verify the public tag matches the reviewed `main` commit and both attachment URLs return HTTP 200.

Release: https://github.com/z13918481356-ship-it/porous-coating-sem-morphometry/releases/tag/v0.2.0

Remote commands used for this standalone project:

```powershell
git remote add origin https://github.com/z13918481356-ship-it/porous-coating-sem-morphometry.git
git remote -v
git push -u origin codex/portfolio-release
```

Never reuse the parent repository remote `metal-oxide-thin-film-ml` for this project.
