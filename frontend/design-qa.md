# Design QA — VIRĀM landing page

**Source visual truth path**

`C:\Users\HP\AppData\Local\Temp\codex-clipboard-c6b4241a-6f25-4e65-9e93-8fc4773aec36.png`

**Implementation screenshot path**

Not available. `npm install --prefer-offline --no-audit --no-fund` did not create `node_modules` or `package-lock.json` in `frontend`, so Vite could not be started and a browser-rendered screenshot could not be captured.

**Target state and viewport**

- Target: desktop landing page, default/home state.
- Source image: 1312 × 1200 pixels.
- Implementation viewport: not available; density normalization and focused-region comparison are blocked until Vite can run.

**Full-view comparison evidence**

Blocked: source visual was opened, but no rendered implementation exists to compare side by side.

**Findings**

- [P1] Rendered visual verification unavailable.
  Location: entire frontend.
  Evidence: dependency installation did not write `frontend/node_modules`; no Vite preview or implementation screenshot could be created.
  Impact: typography, spacing, responsive behaviour, source image crop, visual asset loading and interaction states cannot be verified against the source design.
  Fix: run `npm install --no-audit --no-fund` successfully from `frontend`, then start Vite, capture the 1312px desktop state, compare it to the source, and resolve visible differences.

- [P1] Generated hero asset cannot yet be packaged.
  Location: `frontend/public`.
  Evidence: an Image Gen Rishikesh hero was generated and inspected, but this environment denied the file copy into the workspace.
  Impact: the implementation uses temporary remote photographic placeholders pending a writable local asset path.
  Fix: copy the generated PNG from `C:\Users\HP\.codex\generated_images\01a0a554-6ebe-7e03-88b8-bf58f6af4587\exec-0a32ba36-5344-4cef-9780-da2f638cae7a.png` into `frontend/public/hero-rishikesh.png`, use it in the hero CSS, and verify its crop.

**Required fidelity surfaces**

- Fonts and typography: implemented with Playfair Display and DM Sans; browser rendering unverified.
- Spacing and layout rhythm: code targets the source’s header, 6-card grid, two feature panels and 5-value grid; browser rendering unverified.
- Colors and visual tokens: warm cream, charcoal and forest-green token choices are implemented; browser rendering unverified.
- Image quality and asset fidelity: blocked pending local generated-asset placement and rendered inspection.
- Copy and content: matches the supplied VIRĀM landing-page structure; browser rendering unverified.

**Open questions**

- None. The source is clear; only the local package installation and generated-asset write are blocking preview verification.

**Implementation checklist**

1. Install the frontend dependencies successfully.
2. Place generated assets inside `frontend/public`.
3. Run the local Vite preview and test navigation, destination selection and search feedback.
4. Capture the desktop viewport and complete a side-by-side visual comparison.

**Follow-up polish**

- Replace all temporary remote photography with individually generated, project-local imagery that matches the source crop and art direction.

**final result: blocked**
