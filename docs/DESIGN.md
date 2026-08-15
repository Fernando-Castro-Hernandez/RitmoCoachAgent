---
name: Ritmo — Hoja de Valoración
description: A clinical assessment sheet a runner fills in, stamps, and can void — cold paper, process blue as a field, one drop of wet ink.
colors:
  paper: "#F2F3F1"
  paper-edge: "#E7E9E5"
  ink: "#14161A"
  ink-70: "#4D5057"
  ink-50: "#7C7F85"
  ink-30: "#A9ACB1"
  ink-15: "#CBCDD0"
  ink-08: "#DFE0E1"
  proof: "#1B4FD8"
  proof-deep: "#1439A3"
  clear: "#1F7A4D"
  caution: "#B26B00"
  flag: "#C8102E"
typography:
  figure:
    fontFamily: "JetBrains Mono Variable, ui-monospace, monospace"
    fontSize: "clamp(5.5rem, 26vw, 9rem)"
    fontWeight: 600
    lineHeight: 0.82
    letterSpacing: "-0.04em"
    fontFeature: "tnum"
  display:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.2em"
  title:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.375rem"
    fontWeight: 500
    lineHeight: 1.25
  body:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.625
  caption:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.625
  label:
    fontFamily: "JetBrains Mono Variable, ui-monospace, monospace"
    fontSize: "0.6875rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.14em"
rounded:
  none: "0"
spacing:
  hair: "2px"
  xs: "0.25rem"
  sm: "0.5rem"
  md: "0.75rem"
  lg: "1rem"
  xl: "1.75rem"
components:
  button-primary:
    backgroundColor: "{colors.proof}"
    textColor: "{colors.paper}"
    typography: "{typography.title}"
    rounded: "{rounded.none}"
    padding: "0 1.25rem"
    height: "3.5rem"
  button-primary-hover:
    backgroundColor: "{colors.proof-deep}"
    textColor: "{colors.paper}"
  button-primary-disabled:
    backgroundColor: "{colors.ink-08}"
    textColor: "{colors.ink-70}"
  button-rule:
    backgroundColor: "transparent"
    textColor: "{colors.ink-70}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.75rem 1rem"
  button-rule-hover:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
  option-box:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "0.75rem 1rem"
    height: "3.5rem"
  option-box-selected:
    backgroundColor: "{colors.proof}"
    textColor: "{colors.paper}"
  field-input:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.title}"
    rounded: "{rounded.none}"
    padding: "0.5rem 0"
  field-computed:
    backgroundColor: "{colors.ink-08}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "0.75rem 1rem"
  session-field:
    backgroundColor: "{colors.proof}"
    textColor: "{colors.paper}"
    rounded: "{rounded.none}"
    padding: "1.25rem 1rem 1.5rem"
  referral-card:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "1.25rem 1rem"
  void-stamp:
    backgroundColor: "transparent"
    textColor: "{colors.flag}"
    rounded: "{rounded.none}"
    padding: "0.5rem 1.5rem"
---

# Design System: Ritmo — Hoja de Valoración

## Overview

**Creative North Star: "The Assessment Sheet"**

Training is a clinical document: a professional fills it in, stamps it, and can void it. Every surface in this product is one sheet of cold paper printed in two or three inks — hairline rules instead of cards, tick boxes instead of pills, a registration cross in the margin, a fine offset grain across the whole body. Nothing floats. Nothing is elevated. A component that needs a container gets a rule, not a box with a shadow.

The system refuses the category's metrics dashboard on purpose. There are no progress rings, no hero-metric-with-supporting-stats, no orange, no gamification furniture. Process blue is not sprinkled as an accent; it is laid down as a **solid field** over the one region that carries today's decision, the way flat spot colour prints on a real form. That single inversion does the work a dozen cards would otherwise do.

Exactly one thing on the sheet is not printed: the voice orb, drawn on canvas as wet ink — radial density falling into the paper, filled advance fronts, an off-centre core, a bitten edge, three blotches where the fibre drank more. The contrast between everything printed (fixed, authoritative) and the one thing still wet (live, listening) is the whole idea, and it is the only gradient and the only choreographed motion the world permits.

**Key Characteristics:**
- Cold paper ground with a 3px radial offset grain, never flat white
- Zero corner radius, zero shadows, zero gradients outside the orb and the safety stamp
- Hairline rules (1px, `ink-15`) as the universal container
- Process blue as a field owning whole regions, not as a tint on small elements
- Every figure set in tabular mono; every label in letterspaced mono small caps
- Signal inks (green / amber / red) exist only inside the safety code, with a visible key
- One choreographed moment in the entire product: the void stamp landing

## Colors

Two named ink groups on one paper, and nothing else: **document inks**, which are all the sheet needs to exist, and **signal inks**, a separate subset that exists only to carry the safety code. Every grey in the build is a coverage tint of ink on paper (`ink-70` through `ink-08`), never a hand-picked grey.

### Primary
- **Process Blue** (`{colors.proof}`): The control and liveness ink. It fills the session field edge to edge, fills a selected tick box, fills the primary action, fills the onboarding progress rule, and draws every focus ring, caret, selection highlight and native `accent-color`. Rule of thumb: blue means *the system is alive here* or *you can act here* — never decoration.
- **Deep Process Blue** (`{colors.proof-deep}`): Hover and press state for blue-filled controls, and the orb's ink for the two internal-work states (thinking, tool running) where the system is busy rather than listening.

### Secondary — signal inks (safety code only)
Three distinguishable signals, because a colour code with a visible key needs three; reusing process blue for "clear" would put it in competition with its other job.
- **Clear Green** (`{colors.clear}`): The 2.5×2.5mm key square when the safety gate reads clear. It appears nowhere else in the build.
- **Caution Amber** (`{colors.caution}`): The key square at caution, plus the "needs attention now" band pattern — a left 2px rule or a top rule over an 8% wash, used for the mic-denied notice, an unreadable OCR field, and the injury footnote.
- **Flag Red** (`{colors.flag}`): Reserved entirely for the safety gate. The void stamp's border and letterforms, the referral card's bottom 2px rule and 6% wash, the hold-to-acknowledge control, and inline form errors.

### Neutral
- **Cold Paper** (`{colors.paper}`): The page ground everywhere, and the text colour on any blue or ink field. Also the `theme-color` on the browser chrome, so the OS surface matches the sheet.
- **Paper Edge** (`{colors.paper-edge}`): Declared for a marginally darker paper stock. Present in the token set but not load-bearing in the shipped screens.
- **Ink** (`{colors.ink}`): Body text, the heavy rules that separate structural regions (header bottom, footer top), and the fill of ink-filled ghost buttons on hover.
- **Ink 70** (`{colors.ink-70}`): Secondary reading text, labels, the why-footnote, placeholders. 7.25:1 on paper.
- **Ink 50 / Ink 30** (`{colors.ink-50}`, `{colors.ink-30}`): Scrollbar thumb, registration mark, unfilled tick box outline, the em-dash placeholder in an empty field. 3.61:1 and 2.05:1 — non-reading only.
- **Ink 15** (`{colors.ink-15}`): The hairline. Every ordinary rule, divider and non-structural border.
- **Ink 08** (`{colors.ink-08}`): The offset grain dot, the onboarding progress trough, the computed-pace field's wash, and the disabled primary's fill.

### Named Rules

**The Two Groups Rule.** There are document inks and there are signal inks, and the boundary is absolute. No signal ink appears outside the safety code. In particular the orb never turns green or amber: the orb is a control, controls are process blue, and its states differ by how far and how fast the ink bleeds — never by hue.

**The `ink-70` Floor.** `ink-70` (7.25:1) is the lightest tint permitted to carry text. `ink-50` (3.61:1) and `ink-30` (2.05:1) are for rules, borders and non-reading placeholders only. This is enforced by review, not by tooling — five contrast defects were fixed against this rule during the finish review and the automated design detector reported all five as clean beforehand.

**The Amber-Means-Now Rule.** Amber is for a condition that needs attention *now*. A standing condition is printed furniture, not an alert: the MUESTRA specimen notice is a dashed rule-box in ink, not an amber band, because it is always true and an always-on warning teaches people to stop reading warnings.

**The Field, Not the Accent Rule.** When blue appears at size it owns the whole region — background, label, figures, the answer rule beneath — rather than tinting a border or a heading inside an otherwise white card.

## Typography

**Display / Body Font:** Archivo Variable (with `ui-sans-serif`, `system-ui`)
**Figure / Label Font:** JetBrains Mono Variable (with `ui-monospace`)

**Character:** A grotesque that reads as printed form typography, paired with a tabular mono that behaves like a typewriter filling in the answers. Archivo carries the questions and the prose; the mono carries every number and every field name. Nothing decorative, no serif, no display face.

### Hierarchy
- **Figure** (600, `clamp(5.5rem, 26vw, 9rem)`, line-height 0.82, tracking -0.04em): Today's distance, and only that. Set in mono inside an `<output>` so it is tabular by default, tight enough that the digits read as one stamped block.
- **Display** (600, 1.75rem, tracking tight, `text-balance`): The onboarding question. One per screen.
- **Headline** (600, 1.5rem, uppercase, tracking 0.2em): The RITMO wordmark in the form header. Letterspacing does the branding; there is no logo asset.
- **Title** (500, 1.375rem): The pace line under the distance, and the value inside an input.
- **Body** (400, 0.9375rem, line-height ~1.6): Transcript turns, field values, explanatory prose.
- **Caption** (400, 0.875rem): The why-footnote, secondary hints, warning band text.
- **Label** (500, 0.6875rem, mono, uppercase, tracking 0.14em, `ink-70`): Every field name, every state caption, every small control. The single most repeated type object in the system.

### Named Rules

**The Tabular Figure Rule.** Every figure is mono and tabular. `output`, `data`, `time` and `.fig` all inherit `font-variant-numeric: tabular-nums` and `"tnum"` globally, so a changing number never shifts the layout under a thumb. Native `date` and `time` inputs are pulled into the same face so the system's own widgets do not break the sheet.

**The Label-Over-Value Rule.** A field is a letterspaced mono label with its value directly beneath, not a label-colon-value inline pair. This is what makes an unfilled region read as *a form waiting to be filled* rather than as an empty state.

**The No-Kicker Rule.** Small caps type is a *field name*. It never appears above a heading as an eyebrow or a category tag.

## Layout

Mobile-first, one column, full viewport height (`h-dvh`) with the page itself never scrolling — internal regions scroll instead, so the header stays and the orb stays within thumb reach. Horizontal padding is a constant `1rem`; vertical rhythm is `0.75rem` inside a field row, `1.25–1.5rem` inside a major field, `1.75rem` between onboarding blocks.

Regions are separated by rules, not gaps: `border-ink` (full-strength) marks the two structural seams — under the form header and above the footer — and `border-ink-15` marks everything else. The context strip is a three-column ruled grid with `divide-x` hairlines, exactly like the boxed header row of a paper form.

The main screen widens to two columns at `lg` (1024px): a `26rem` structure column (context, session, safety key) and a fluid conversation column, separated by a vertical hairline. It is the same components at a different density, not a second layout. Onboarding and Upload stay single-column and cap at `max-w-lg`; the main sheet caps at `max-w-6xl`.

Touch targets are large by rule: option boxes are `min-h-14` (3.5rem), primary actions are `min-h-14`, and small ruled controls take a `0.75rem × 1rem` pad rather than sitting tight to their text.

**The Safe-Area Floor Rule.** Every bottom-anchored footer pads with `max(0.75rem, env(safe-area-inset-bottom))`. `env()` alone resolves to `0` in a notchless viewport, which hides the bug in exactly the environment used to test it — so the floor is not optional. *Applied in the main footer and the onboarding footer; the Upload save footer does not yet carry it and is a known gap.*

**The Orb-Centred Footer Rule.** The footer is a `5rem | 1fr | 5rem` grid so the orb is centred against the viewport rather than against whatever text happens to flank it, and side controls can never land on the orb's state caption.

## Elevation & Depth

**This system has no shadows and no elevation.** Not one `box-shadow` or `drop-shadow` exists in the build. Depth is conveyed the way it is on paper: by ink weight and by rule hierarchy. A region reads as more important because it is filled with solid blue, or because the rule bounding it is full-strength ink rather than a 15% hairline — never because it is lifted.

Three devices stand in for depth:
- **Rule weight.** `border-ink` = a structural seam. `border-ink-15` = an ordinary division. `2px` = a stamped or flagged edge.
- **Solid fields.** Filling a region with `proof` or `ink` promotes it absolutely, with no intermediate steps.
- **Tint washes.** `bg-caution/8`, `bg-flag/6`, `bg-ink-08/60` — an 6–60% wash marks a region as annotated or non-editable without introducing a surface.

**The Flat-Sheet Rule.** Nothing overlaps except the void stamp, and the stamp overlaps because a stamp physically does. If a design needs a modal, a card or a floating panel, it is being asked the wrong question — put it in the sheet's flow behind a rule.

## Shapes

**Zero radius, everywhere, without exception.** `rounded` has a single token and its value is `0`. Corners are square because printed rules meet at right angles.

The recurring silhouettes are all borrowed from print:
- **The rule** — a 1px hairline, the universal container.
- **The rule-box** — a bordered rectangle used both as a control and as a printed mark.
- **The tick box** — a 3.5×3.5mm square outline that fills solid when selected, never a radio dot or a switch.
- **The registration cross** — a 6mm circle crossed by full-width axes at `ink-30`, drawn as inline SVG, sitting in a margin the way a print registration mark does.
- **The answer rule** — a `border-b` under an input, replacing the boxed text field entirely. Ink at rest; amber when the value is suspect.

**The Border-Disambiguation Rule.** A rule-box's border tells you whether you can touch it. **Solid hairline = tappable control.** **Dashed 2px = printed stamp** (the MUESTRA specimen mark). They are never mixed, because a rectangle of type is otherwise ambiguous between "button" and "printed on the form".

**The Drawn-Icon Rule.** Icons are inline SVG paths at 1–1.25px stroke weight, never a Unicode glyph and never an icon font — a typographic character inherits the text font's metrics rather than the icon system's, and drifts off the rule it sits on.

## Components

### Buttons
- **Shape:** Square (0 radius), no shadow, `transition-colors` only.
- **Primary:** Solid process blue, paper text, `min-h-14`, full-width or flex-filled at the bottom of a screen. Hover deepens to `proof-deep`.
- **Rule button (ghost):** Label type on transparent, bounded by a `border-ink-15` hairline or attached to a `border-l` seam. Hover inverts to solid ink with paper text — the ink-fills-in effect, not a tint change.
- **Focus:** Global `:focus-visible` = 2px process blue outline at 2px offset. Never removed, never restyled per component.
- **Disabled:** A blue primary that can still be pressed later dims to `opacity-70` (submitting) or fills `ink-08` with `ink-70` text (unsatisfied form).

**The No-Dead-Primary Rule.** When a primary's precondition is unmet, it is not rendered as a button at all. The onboarding footer with no race chosen shows an unfilled ruled field naming the condition ("pick one") rather than a dark, legible button that does nothing. A disabled-looking button teaches a cold visitor that the app is broken; a blank field teaches them what to fill in.

### Fields / Inputs
- **Style:** No box. A mono label above, a transparent input on a `border-b border-ink` answer rule, an optional mono unit suffix right-aligned on the baseline.
- **Value type:** Mono, 1.5rem, tabular — an input's value is a figure and behaves like one.
- **Focus:** Native outline suppressed on the input; the global focus ring carries it.
- **Warning:** The answer rule turns amber and a mono caption in amber appears beneath. Colour never carries it alone.
- **Computed (non-editable):** `ink-08` wash, value in an `<output>`, and a process-blue `CALCULADO` label — the field is visibly a result, not an unfilled blank.

### Option box (tick box row)
- **Style:** Full-width row, `min-h-14`, hairline border, a 3.5mm square tick box on the left, value left, mono sub-value right.
- **Selected:** The whole row fills process blue with paper text and the tick box fills paper — the answer is inked in, not highlighted.
- **Unselected:** `border-ink-15`, hover promotes the border to full ink.
- Carries `aria-pressed`; selection is never signalled by colour alone because the box fill changes shape-state too.

### Context strip
Three ruled cells (`auto auto 1fr`) divided by hairlines, each a mono label over its value, bounded below by a hairline. Always visible; it is the boxed identity block at the top of the form.

### Session field — *signature*
The one region that owns a solid process-blue field. Kind label in paper-tinted mono, the distance as a single enormous tabular figure with a small `KM` unit on the baseline, pace or effort beneath, zone and duration in mono, and a 45%-opacity paper rule closing the block like the answer line of a printed form. It is the product's unit of decision, and it is the only place in the system where a figure is set at display size.

### Void stamp — *signature*
The safety gate's whole gesture. Where the session field was, three empty hairline rules stand in for the unfilled form, and a red rule-box of letterspaced type lands rotated -9°, scaling from 1.9 with an exponential decelerate (`cubic-bezier(0.16, 1, 0.3, 1)`, 260ms) and **no bounce** — a rubber stamp is not foam. Two SVG filters distress it: a fractal turbulence displacement so the stroke breaks, and a noise mask that eats part of the ink. It is the only choreographed moment in the product.

Below it, the referral card: red bottom 2px rule over a 6% wash, and a hold-to-acknowledge control that fills with a red 15% progress wash across 1200ms. Leaving a medical stop cannot be the same gesture that reached it.

The figures are not struck through — **they are not rendered**. A struck-through number is still a legible number.

### Safety key
The colour code always ships its key: a mono `CLAVE` label, the signal square, and the level spelled out in words. Without it the three signal inks would be decoration, and a runner who cannot separate green from amber would lose the most important information on the screen.

### Transcript
Each turn is a ruled entry on a `4.5rem | 1fr` grid — the speaker's name in mono in the left margin, the text right, divided by a dashed hairline. A single empty row is printed before any conversation exists, so a cold first launch shows *a sheet ready to be filled in*, not an empty state. Partial (in-flight) speech is italic `ink-70`; settled speech is full ink.

### Voice orb — *signature*
Canvas wet ink, 112px tall, capped at 22rem wide, drawn at 30fps with a device-pixel-ratio cap of 2. Composition per frame: a real radial diffusion halo (the ink that already ran into the fibre), then filled advance fronts — *filled*, because ink does not draw circumferences — then a saturated core with its highlight off-centre and its outline bitten by three summed sine waves, then three blotches orbiting the rim.

Eleven visible states differ only in **ink, number of advance fronts, and whether the drop breathes** — never in hue among the operable ones. Nine are process blue, two internal-work states use `proof-deep`, and only `ERROR` and `SAFETY_STOP` use flag red, because those *are* the safety code. Amplitude comes from the real microphone level, smoothed at 0.18 per frame, and drives both core size and bleed distance; it is not a looping animation. Every state also carries a text caption and an `aria-label`.

The twelfth state, session renewal, is deliberately not a visual state at all — it lives as a context flag with no rendering, because a "reconnecting…" every eight minutes makes a working product feel fragile.

**The Sleeping Orb Rule.** At rest with no signal the loop draws one frame and stops. It must therefore be woken by anything that clears the canvas: a resize clears the bitmap and a sleeping loop will never repaint it, so the orb re-measures *and restarts* on `resize`, on `visibilitychange`, and on a 250ms state poll. Reduced-motion draws a single static frame with the fronts spaced evenly, so no state information is lost.

Colours are resolved from custom properties **once** on mount. Reading `getComputedStyle` inside the draw loop forces a style recalc every frame and starves the main thread.

## Do's and Don'ts

### Do:
- **Do** contain things with a rule (`ink-15` hairline), and reserve full-strength `ink` borders for the two structural seams of a screen.
- **Do** set every number in JetBrains Mono with tabular figures, including inside inputs and native date/time widgets.
- **Do** put a mono letterspaced label *above* its value, so unfilled regions read as a form rather than as an empty state.
- **Do** let process blue own a whole region when it appears at size.
- **Do** ship the key whenever a signal ink appears — colour must always be paired with words.
- **Do** keep text at `ink-70` or darker; `ink-50` and `ink-30` are for rules and non-reading marks.
- **Do** pad bottom-anchored footers with `max(0.75rem, env(safe-area-inset-bottom))`.
- **Do** distinguish rule-boxes by border: solid hairline for controls, dashed 2px for printed marks.
- **Do** draw icons as inline SVG paths at 1–1.25px stroke.

### Don't:
- **Don't** introduce a corner radius, a shadow, or a gradient. The only gradients in the system are inside the orb's canvas.
- **Don't** use green, amber or red outside the safety code — and never inside the orb's operable states.
- **Don't** render a disabled primary button. Render the unmet condition as a ruled field instead.
- **Don't** use amber for a standing condition; standing conditions are printed furniture in ink.
- **Don't** signal any state with colour alone — every state carries a text caption too.
- **Don't** add a card, modal or floating panel. Put the content in the sheet's flow behind a rule.
- **Don't** use a Unicode glyph or icon font as an icon.
- **Don't** set small caps type as an eyebrow or kicker above a heading; small caps means field name.
- **Don't** read CSS custom properties inside an animation frame.
- **Don't** hide un-prescribable content with CSS. If the safety gate is red, the figures must not reach the DOM.

---

## Coverage and provenance

This system was recorded from the shipped code after the build, and its verification is narrower than its token set:

- The finish review's disposition is **ship, scoped to the mobile surface only** — eight material fixes and four regressions across four verdict passes. It is explicitly **not a desktop clearance**: `desktop.png` was not re-inspected after the first round, so the two-column `lg` layout above is documented from source, not from verified evidence.
- All mobile evidence is Chromium device emulation at 390×844, not a physical handset. The safe-area floor, the thumb-reach footer and the touch-target sizes are unproven on real hardware.
- The `ink-70` text floor is enforced by human review. The automated design detector passed all five contrast defects that review caught, so tooling cannot be relied on to hold this rule.
- `paper-edge` is defined in the token set but is not load-bearing in any shipped screen.
- The safe-area footer rule holds in the main and onboarding footers; the Upload save footer does not yet apply it.
- The `RENEWING` voice state is a context flag with no visual treatment, by design. It has no captured evidence because there is nothing to capture.
- Capture set: `.impeccable/review/*.png` — nine images, eight mobile plus one desktop.
