# Technical report

- `ClaimGuard_Technical_Report.tex`: editable IMRAD source.
- `ClaimGuard_Technical_Report.pdf`: final compiled report.
- `CAPSTONE_REPORT_OUTLINE.md`: compact content outline.

Build twice from the repository root so references settle:

```powershell
Set-Location docs/report
pdflatex -interaction=nonstopmode -halt-on-error ClaimGuard_Technical_Report.tex
pdflatex -interaction=nonstopmode -halt-on-error ClaimGuard_Technical_Report.tex
Set-Location ../..
```

The title page, references, and appendix are outside the eight-page main-text count.
