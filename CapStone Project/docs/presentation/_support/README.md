# Presentation

Preferred submission/demo files:

- `ClaimGuard_Capstone_Praesentation_DE_mit_UI_Demo.pptx`
- `ClaimGuard_Capstone_Praesentation_DE_mit_UI_Demo.pdf`
- `_support/ClaimGuard_Praesentation_Notizen_DE.md`

Regenerate the editable English and German decks from the repository root:

```powershell
python docs/presentation/source/generate_presentation.py
python docs/presentation/source/translate_presentation_de.py
```

On Windows with PowerPoint installed, rebuild the German deck with embedded UI video:

```powershell
& .\docs\presentation\source\build_demo_presentation.ps1
```

The module-coverage slide states the evidence boundary explicitly: Core Modules 1--3 and
Optional Modules 4--5 are complete; Module 6 remains a comparison scaffold/future benchmark.
