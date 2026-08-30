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
- [x] No remote push or public release has been performed.

## Before creating the public GitHub repository

- [ ] Confirm the public repository name; recommended: `porous-coating-sem-morphometry`.
- [ ] Confirm that `Yuexuan Zhu` is the desired public citation author name.
- [ ] Create an empty GitHub repository without generating another README, license, or `.gitignore`.
- [ ] Add the new repository URL to `CITATION.cff` as `repository-code`.
- [ ] Add the new remote and verify it does not point to the unrelated parent project.
- [ ] Push `codex/portfolio-release`, review the rendered README and Actions result, then merge or rename it to the desired default branch.
- [ ] Optionally attach the DOCX/PDF report to a GitHub Release; do not attach source-data archives or redistributed model-development data without rechecking license and size policy.

Suggested remote commands after the repository is created:

```powershell
git remote add origin https://github.com/<account>/porous-coating-sem-morphometry.git
git remote -v
git push -u origin codex/portfolio-release
```

Never reuse the parent repository remote `metal-oxide-thin-film-ml` for this project.
