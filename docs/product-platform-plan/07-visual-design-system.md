# Ophanix Visual Design System

This document captures the UI and styling language of `ophanix-site` and translates it into implementation guidance for refactoring `ophanix-platform` so the product app shares the same visual identity.

Source references:

- Site global theme: `ophanix-site/src/app/globals.css`
- Site layout and page assembly: `ophanix-site/src/app/page.tsx`
- Site navigation: `ophanix-site/src/components/Navigation.tsx`
- Site hero and calls to action: `ophanix-site/src/components/Hero.tsx`, `ophanix-site/src/components/CTA.tsx`
- Site content grids: `ophanix-site/src/components/Problem.tsx`, `Features.tsx`, `HowItWorks.tsx`
- Site motion/imagery: `LiquidGradientBackground.tsx`, `OpeningOverlay.tsx`
- Platform target primitives: `packages/product-platform/frontend/src/components/ui/*`
- Platform target shell: `packages/product-platform/frontend/src/components/layout/*`

## Design Goal

The site identity is dark, cinematic, precise, and editorial. It should make `ophanix-platform` feel like a security control plane from the same product family, not a generic light SaaS dashboard.

The platform should keep its dense operational UX, but adopt the site's visual DNA:

- Deep navy global canvas
- Warm cream foreground
- High-contrast rectangular controls
- Hairline borders instead of card shadows
- Large display typography for page titles, empty states, and metrics
- Uppercase, tracked labels for navigation and system metadata
- Minimal radius
- Sparse, deliberate accent colors
- Motion that feels fluid and technical, not playful

## Color Palette

### Core Colors

| Token | Hex | HSL | Usage |
| --- | --- | --- | --- |
| `--background` | `#071525` | `212 68% 9%` | Global page/app background |
| `--background-deep` | `#0A0E27` | `232 59% 10%` | Hero, overlays, deep panels, visual backgrounds |
| `--foreground` | `#FFEDCE` | `38 100% 90%` | Primary text, brand mark, filled button background |
| `--muted` | `rgba(255, 237, 206, 0.55)` | n/a | Eyebrows, secondary text, inactive nav |
| `--accent` | `#FFEDCE` | `38 100% 90%` | Main action/accent, focus ring |
| `--border` | `rgba(255, 237, 206, 0.15)` | n/a | Dividers, card/table gridlines |

### Motion And Shader Accents

| Token | Hex | HSL | Usage |
| --- | --- | --- | --- |
| `--accent-warm` | `#F15A22` | `16 88% 54%` | Hero gradient warmth, warning accent |
| `--accent-teal` | `#40E0D0` | `174 72% 56%` | Hero gradient, secure/healthy state accent |
| `--accent-danger` | `#E03E4E` | `354 72% 56%` | Hero gradient, critical/error accent |

### Opacity Scale

Use opacity to create most hierarchy. Do not introduce many extra grays.

| Token | Value | Usage |
| --- | --- | --- |
| `text-primary` | `foreground / 100%` | Main headings, active text |
| `text-secondary` | `foreground / 70%` | Body copy and table primary descriptions |
| `text-muted` | `foreground / 55%` | Labels, helper text, inactive links |
| `text-subtle` | `foreground / 40%` | Metadata, captions, timestamps |
| `text-disabled` | `foreground / 25%` | Disabled controls |
| `surface-muted` | `foreground / 4% to 8%` | Hover surfaces, subtle fills |
| `border-default` | `foreground / 15%` | Standard borders |
| `border-strong` | `foreground / 60% to 70%` | Buttons, active controls |

### Platform Token Mapping

The current platform uses shadcn-style HSL CSS variables. Replace the light theme with dark Ophanix tokens while preserving the variable API so existing components keep working.

```css
:root {
  --background: 212 68% 9%;
  --foreground: 38 100% 90%;

  --card: 212 68% 9%;
  --card-foreground: 38 100% 90%;

  --primary: 38 100% 90%;
  --primary-foreground: 212 68% 9%;

  --secondary: 38 100% 90%;
  --secondary-foreground: 212 68% 9%;

  --muted: 212 45% 13%;
  --muted-foreground: 38 100% 90%;

  --accent: 38 100% 90%;
  --accent-foreground: 212 68% 9%;

  --destructive: 354 72% 56%;
  --destructive-foreground: 38 100% 90%;

  --border: 38 100% 90%;
  --input: 38 100% 90%;
  --ring: 38 100% 90%;

  --accent-warm: 16 88% 54%;
  --accent-teal: 174 72% 56%;
  --accent-danger: 354 72% 56%;

  --radius: 0rem;
}
```

Important: because `border` and `input` use the foreground hue, component classes must apply opacity, for example `border-foreground/15`, `border-input/15`, or `border-border/15`. Do not use full-strength `border` by default.

## Typography

### Font Families

The site defines local fonts in `ophanix-site/public/fonts`.

| Token | Font | Source weights | Usage |
| --- | --- | --- | --- |
| `font-display` | `Sagittaire` | 400, 500, 700 | Editorial headings, hero titles, page titles, large numbers |
| `font-body` | `PolySans` | 300, 400, 500 | Body copy, navigation, buttons, forms, tables |

Recommended platform setup:

```css
@font-face {
  font-family: "Sagittaire";
  src: url("/fonts/sagittaire/Sgtt-Display-Trial-Regular.otf") format("opentype");
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: "Sagittaire";
  src: url("/fonts/sagittaire/Sgtt-Display-Trial-Medium.otf") format("opentype");
  font-weight: 500;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: "Sagittaire";
  src: url("/fonts/sagittaire/Sgtt-Display-Trial-Bold.otf") format("opentype");
  font-weight: 700;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: "PolySans";
  src: url("/fonts/polysans/polysanstrial-neutral.otf") format("opentype");
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: "PolySans";
  src: url("/fonts/polysans/polysanstrial-median.otf") format("opentype");
  font-weight: 500;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: "PolySans";
  src: url("/fonts/polysans/polysanstrial-slim.otf") format("opentype");
  font-weight: 300;
  font-style: normal;
  font-display: swap;
}
```

Recommended Tailwind extension:

```ts
fontFamily: {
  display: ["Sagittaire", "serif"],
  body: ["PolySans", "ui-sans-serif", "system-ui", "sans-serif"],
  sans: ["PolySans", "ui-sans-serif", "system-ui", "sans-serif"]
}
```

### Type Scale

Use the site's scale for high-impact surfaces, then compress carefully for product density.

| Role | Classes | Notes |
| --- | --- | --- |
| Hero title | `font-display font-medium text-[3rem] sm:text-[4rem] lg:text-[5rem] leading-[0.95] tracking-tight` | Marketing-only or login splash |
| Product page title | `font-display font-medium text-4xl sm:text-5xl leading-[1.05] tracking-tight` | Top-level platform pages |
| Section heading | `font-display font-medium text-3xl sm:text-4xl leading-[1.05] tracking-tight` | Major dashboard regions |
| Panel heading | `font-body font-medium text-xl leading-tight` | Cards, drawers, modals |
| Metric number | `font-display text-5xl lg:text-6xl leading-none` | KPI cards and large statistics |
| Body large | `font-body text-lg leading-relaxed text-foreground/70` | Page descriptions |
| Body default | `font-body text-base leading-relaxed text-foreground/70` | Descriptive copy |
| Product body | `font-body text-sm leading-5 text-foreground/65` | Tables, dense pages |
| Eyebrow | `text-xs sm:text-sm uppercase tracking-[0.2em] text-foreground/55` | Section labels, card categories |
| Metadata | `text-xs tracking-wide text-foreground/40` | Captions, timestamps |
| Buttons/nav | `font-body text-sm uppercase tracking-[0.1em]` | Controls and navigation |

### Typography Rules

- Use `Sagittaire` sparingly but visibly. It should define identity, not reduce dashboard scanability.
- Do not use negative letter spacing except `tracking-tight` on large display headings.
- Do not scale fonts with viewport units.
- Use uppercase tracking for navigation, labels, badges, and control-plane metadata.
- Body copy should almost never be pure `foreground`; use `foreground/60` to `foreground/75`.
- Product table text should remain compact and readable; do not use display type in table rows.

## Layout System

### Containers

Site container:

```tsx
"max-w-6xl mx-auto px-6 lg:px-8"
```

Narrow container:

```tsx
"max-w-3xl mx-auto px-6 lg:px-8"
```

CTA container:

```tsx
"max-w-4xl mx-auto text-center"
```

Platform app content:

```tsx
"mx-auto w-full max-w-[1440px] px-6 py-6"
```

Do not place the entire app in a white or light gray shell. The app background should be `bg-background`.

### Section Spacing

Marketing pages:

```tsx
"py-32 lg:py-40 px-6 lg:px-8"
"py-32 lg:py-48 px-6 lg:px-8"
```

Platform pages:

```tsx
"space-y-6 p-6"
"grid gap-4 md:grid-cols-2 xl:grid-cols-3"
"grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]"
```

Use large vertical breathing room for static information pages, but keep platform workflows dense enough for repeated work.

### Grid Pattern

The most important reusable site pattern is a hairline grid:

```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-foreground/15">
  <div className="bg-background p-8 lg:p-10">...</div>
</div>
```

Platform adaptation:

```tsx
<div className="grid gap-px overflow-hidden border border-foreground/15 bg-foreground/15 md:grid-cols-2 xl:grid-cols-3">
  <section className="bg-background p-5">...</section>
</div>
```

Use this for metric groups, settings groups, module lists, and overview summaries.

### Responsiveness

Desktop:

- Use 12-column compositions for editorial sections.
- Common split: `lg:grid-cols-12`, left `lg:col-span-4`, right `lg:col-span-8`.
- Product app sidebar can remain fixed at `w-72`, but restyle it with Ophanix tokens.

Tablet:

- Use 2-column content grids.
- Navigation may become crowded at `768px`; platform should use compact side/top navigation earlier than the marketing site.

Mobile:

- Stack all grids into single columns.
- Buttons should become full width only when the action group is narrow.
- Maintain `px-6`.
- Use `100dvh` for splash/hero overlays.
- Avoid horizontal tables without wrappers. Use `overflow-x-auto` for dense data.

## Core Components

### Button

Site behavior:

- Rectangular, no radius.
- Uppercase tracked label.
- Border `rgba(255, 237, 206, 0.7)`.
- Primary starts filled cream with navy text.
- Secondary starts transparent with cream text.
- Hover uses a horizontal fill wipe over `420ms cubic-bezier(0.22, 1, 0.36, 1)`.

Marketing button classes:

```tsx
"relative inline-flex items-center justify-center overflow-hidden border border-foreground/70 px-9 py-[1.125rem] text-base font-normal uppercase tracking-[0.1em] transition-colors"
```

Platform button base:

```tsx
"inline-flex h-10 items-center justify-center gap-2 border px-4 text-sm font-medium uppercase tracking-[0.1em] transition-colors duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/90 focus-visible:ring-offset-4 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-40"
```

Variants:

| Variant | Classes |
| --- | --- |
| Primary | `border-foreground/70 bg-foreground text-background hover:bg-transparent hover:text-foreground` |
| Secondary | `border-foreground/70 bg-transparent text-foreground hover:bg-foreground hover:text-background` |
| Ghost | `border-transparent bg-transparent text-foreground/70 hover:text-foreground hover:bg-foreground/5` |
| Destructive | `border-[hsl(var(--accent-danger))]/70 bg-[hsl(var(--accent-danger))] text-foreground hover:bg-transparent hover:text-[hsl(var(--accent-danger))]` |

Icon buttons should use Lucide icons, square dimensions, and no text where the icon is conventional.

### Inputs And Selects

Use rectangular controls with cream hairlines:

```tsx
"flex h-10 w-full border border-foreground/15 bg-background px-3 py-2 text-sm text-foreground outline-none transition-colors placeholder:text-foreground/40 focus-visible:border-foreground/60 focus-visible:ring-2 focus-visible:ring-foreground/70 disabled:cursor-not-allowed disabled:opacity-40"
```

Rules:

- Do not use light fills.
- Do not use blue focus rings.
- Use `text-foreground/40` for placeholders.
- Label text should be `text-sm font-medium text-foreground/70`.
- Helper text should be `text-xs text-foreground/45`.

### Cards And Panels

The site does not use rounded card-heavy SaaS styling. It uses dark cells separated by hairline borders.

Default product card:

```tsx
"border border-foreground/15 bg-background text-foreground"
```

Card header:

```tsx
"space-y-1.5 border-b border-foreground/15 p-5"
```

Card title:

```tsx
"font-body text-base font-medium leading-none text-foreground"
```

Card description:

```tsx
"text-sm leading-5 text-foreground/60"
```

Avoid `shadow-sm` by default. Use borders and spacing to create structure.

### Metric Cards

Recommended structure:

```tsx
<section className="border border-foreground/15 bg-background p-5">
  <p className="text-xs uppercase tracking-[0.2em] text-foreground/45">Policy decisions</p>
  <p className="mt-4 font-display text-5xl leading-none text-foreground">2,418</p>
  <p className="mt-3 text-sm leading-5 text-foreground/60">Last 24 hours</p>
</section>
```

Metric numbers should use `Sagittaire`; labels and descriptions should use `PolySans`.

### Modals

Site influence:

- Dark content
- Cream text
- Strong focus state
- Minimal radius
- Overlay opacity is functional, not decorative

Dialog overlay:

```tsx
"fixed inset-0 z-50 bg-black/45"
```

Dialog content:

```tsx
"fixed left-1/2 top-1/2 z-50 w-[min(92vw,32rem)] -translate-x-1/2 -translate-y-1/2 border border-foreground/15 bg-background p-5 text-foreground shadow-[0_24px_80px_rgba(0,0,0,0.45)]"
```

### Drawers

Use drawers for dense object detail. Keep the platform's existing right-side drawer model but restyle:

```tsx
"fixed right-0 top-0 flex h-full w-[min(100vw,46rem)] flex-col border-l border-foreground/15 bg-background shadow-[0_24px_80px_rgba(0,0,0,0.45)]"
```

Drawer tabs:

```tsx
"flex gap-px border border-foreground/15 bg-foreground/15 p-0"
```

Active tab:

```tsx
"bg-foreground text-background"
```

Inactive tab:

```tsx
"bg-background text-foreground/60 hover:text-foreground"
```

### Navigation

Site nav:

- Fixed top
- `h-20`
- Cream brand mark and uppercase nav items
- Blurs up to `12px` on scroll
- Border fades in with scroll
- Optional dotted texture overlay

Platform shell adaptation:

- Sidebar background: `bg-background`
- Sidebar border: `border-foreground/15`
- Brand block: logo plus uppercase `OPHANIX`, tracking wide
- Area headings: `text-xs uppercase tracking-[0.2em] text-foreground/40`
- Nav items: `text-sm uppercase tracking-[0.08em]`
- Active nav: cream fill, navy text
- Inactive nav: cream muted, hover cream text and subtle cream fill

Sidebar item:

```tsx
active
  ? "bg-foreground text-background"
  : "text-foreground/55 hover:bg-foreground/5 hover:text-foreground"
```

Top bar:

```tsx
"flex h-16 items-center justify-between border-b border-foreground/15 bg-background/95 px-6 backdrop-blur-xl"
```

### Tables

Tables should be dense but visually aligned to the site grid.

Container:

```tsx
"overflow-hidden border border-foreground/15 bg-background"
```

Table:

```tsx
"w-full caption-bottom text-sm"
```

Header cells:

```tsx
"h-10 px-3 text-left align-middle text-xs font-medium uppercase tracking-[0.16em] text-foreground/45"
```

Rows:

```tsx
"border-b border-foreground/10 transition-colors hover:bg-foreground/[0.04]"
```

Cells:

```tsx
"p-3 align-middle text-foreground/70"
```

Use `font-medium text-foreground` only for primary row identifiers.

### Tabs

Use a segmented rectangular tab bar.

Tab list:

```tsx
"flex gap-px border border-foreground/15 bg-foreground/15"
```

Tab:

```tsx
"flex-1 bg-background px-3 py-2 text-sm font-medium uppercase tracking-[0.08em] text-foreground/55 transition-colors hover:text-foreground"
```

Active:

```tsx
"bg-foreground text-background"
```

### Badges

Base:

```tsx
"inline-flex items-center border px-2 py-0.5 text-xs font-medium uppercase tracking-wide"
```

Tones:

| Tone | Classes |
| --- | --- |
| Default | `border-foreground/20 bg-foreground/10 text-foreground/80` |
| Success | `border-[hsl(var(--accent-teal))]/40 bg-[hsl(var(--accent-teal))]/10 text-[hsl(var(--accent-teal))]` |
| Warning | `border-[hsl(var(--accent-warm))]/40 bg-[hsl(var(--accent-warm))]/10 text-[hsl(var(--accent-warm))]` |
| Danger | `border-[hsl(var(--accent-danger))]/40 bg-[hsl(var(--accent-danger))]/10 text-[hsl(var(--accent-danger))]` |
| Muted | `border-foreground/15 bg-transparent text-foreground/45` |

## Border Radius, Shadows, And Elevation

### Radius

The site uses square geometry. Platform defaults should move away from `rounded-lg`.

| Token | Value | Usage |
| --- | --- | --- |
| `radius-none` | `0` | Buttons, cards, tables, nav, panels |
| `radius-sm` | `2px` | Tiny badges or focus-preserving controls only |
| `radius-md` | `4px` | Rare: popovers where platform usability requires it |

Do not use `rounded-xl`, pills, or soft SaaS cards.

### Shadows

Default surfaces should have no shadow.

| Token | Value | Usage |
| --- | --- | --- |
| `shadow-none` | `none` | Cards, tables, app panels |
| `shadow-overlay` | `0 24px 80px rgba(0,0,0,.45)` | Dialogs, drawers, popovers |
| `shadow-logo` | `0 0 24px rgba(255,237,206,.22)` | Brand/logo overlays only |

## Interaction States

### Hover

- Text links: `hover:text-foreground transition-colors`
- Rows: `hover:bg-foreground/[0.04]`
- Secondary button: fill cream on hover
- Primary button: remove cream fill on hover for marketing CTA; for dense product actions, use a simpler background/text inversion

### Focus

Global site focus:

```css
:focus:not(:focus-visible) {
  outline: none;
}

:focus-visible {
  outline: 2px solid rgba(255, 237, 206, 0.9);
  outline-offset: 4px;
}
```

Platform controls can use Tailwind rings, but they must visually match the cream outline:

```tsx
"focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-foreground/90 focus-visible:ring-offset-4 focus-visible:ring-offset-background"
```

### Active

- Active navigation and active tabs should invert: cream fill, navy text.
- Pressed buttons can use `scale` only if subtle. Prefer color inversion.
- Dragging marquees or timelines should use `cursor-grabbing`.

### Motion

Site timings:

| Motion | Duration | Easing |
| --- | --- | --- |
| CTA wipe | `420ms` | `cubic-bezier(0.22, 1, 0.36, 1)` |
| Nav height/border | `300ms` | `ease-out` |
| Mobile menu content fade | `220ms` | `ease-out` |
| Opening overlay fade | `650ms` | `ease-out` |
| Logo overlay fade | `200ms in`, `500ms out` | `ease-out` |

Reduced motion:

- Disable shader loops.
- Disable infinite marquees.
- Set transition and animation duration near zero.
- Keep focus and active states visible without motion.

## Icon And Imagery Style

### Logo

Use the cream monochrome Ophanix mark on dark background. In platform, the sidebar brand should include:

- Logo at `40px` to `48px`
- `OPHANIX` in `PolySans`, bold, uppercase, tracking wide
- Optional product descriptor in muted small text

### Icons

The platform already uses `lucide-react`. Keep this.

Rules:

- Size: `h-4 w-4` for table/actions, `h-5 w-5` for primary nav/panels.
- Stroke style: default Lucide line icons.
- Color: `text-foreground/55` default, `text-foreground` active.
- Semantic accents only for status, not decoration.
- Do not introduce filled colorful icon sets.

### Imagery

The site's primary imagery is generated at runtime with Three.js:

- Liquid gradient
- Deep navy base
- Warm orange, teal, rose highlights
- Fine grain
- Pointer/touch ripples
- Radial dark vignette

Platform use:

- Login screen can reuse a static or live liquid-gradient background.
- Overview page can use a subtle hero band with the gradient masked behind content.
- Do not use stock imagery.
- Do not use decorative orb backgrounds.
- Do not make charts compete with the shader. Charts should stay flat and data-first.

## Visual Tone And UX Feel

The design should feel:

- Operational, not decorative
- Serious, not sterile
- Editorial, not generic SaaS
- Precise, not crowded
- High-trust, security-forward, and deterministic

Copy and UI labels should be short, direct, and system-oriented. Prefer phrases like:

- Runtime control
- Policy decisions
- Trust posture
- Execution supervision
- Audit trail
- Agent identity
- Enforcement result

Avoid chatty helper copy inside the application. Use dense labels and clear affordances.

## Responsive Behavior

### Desktop

- Fixed sidebar plus topbar is acceptable.
- Use `max-w-[1440px]` for wide dashboards.
- Use three-column grids for module cards and metrics.
- Use split layouts for detail pages: main content plus right rail.

### Tablet

- Convert three-column grids to two columns.
- Keep topbar controls visible if they fit.
- Collapse secondary controls into popovers when necessary.
- Avoid marketing nav behavior in the platform at tablet widths if it causes crowding.

### Mobile

- Sidebar should become drawer or bottom-access nav.
- Topbar should prioritize title, environment, and alerts.
- Data tables need horizontal scroll wrappers or stacked row summaries.
- Action bars should wrap.
- Buttons in action groups can become full width.

## Reusable Patterns

### Pattern: Page Header

```tsx
<header className="border-b border-foreground/15 bg-background px-6 py-6">
  <p className="text-xs uppercase tracking-[0.2em] text-foreground/45">Runtime control</p>
  <div className="mt-3 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
    <div>
      <h1 className="font-display text-4xl font-medium leading-[1.05] tracking-tight text-foreground">
        Policy decisions
      </h1>
      <p className="mt-3 max-w-3xl text-sm leading-5 text-foreground/65">
        Review every intercepted tool call before execution.
      </p>
    </div>
    <Button>Export audit trail</Button>
  </div>
</header>
```

### Pattern: Hairline Module Grid

```tsx
<div className="grid gap-px border border-foreground/15 bg-foreground/15 md:grid-cols-2 xl:grid-cols-3">
  {items.map((item) => (
    <section className="bg-background p-6" key={item.id}>
      <p className="text-xs uppercase tracking-[0.2em] text-foreground/45">{item.kicker}</p>
      <h2 className="mt-4 font-body text-2xl font-medium text-foreground">{item.title}</h2>
      <p className="mt-4 text-sm leading-5 text-foreground/60">{item.description}</p>
    </section>
  ))}
</div>
```

### Pattern: Dense Data Panel

```tsx
<section className="border border-foreground/15 bg-background">
  <div className="flex items-center justify-between border-b border-foreground/15 p-5">
    <div>
      <h2 className="text-base font-medium text-foreground">Recent decisions</h2>
      <p className="mt-1 text-sm text-foreground/55">Live gateway enforcement results</p>
    </div>
    <Button variant="secondary">View all</Button>
  </div>
  <DataTable columns={columns} items={items} getKey={(item) => item.id} />
</section>
```

### Pattern: Empty State

```tsx
<div className="border border-dashed border-foreground/20 bg-background p-8">
  <p className="text-xs uppercase tracking-[0.2em] text-foreground/45">No events</p>
  <h2 className="mt-4 font-display text-4xl font-medium leading-[1.05] text-foreground">
    Nothing has reached this policy yet.
  </h2>
  <p className="mt-4 max-w-xl text-sm leading-5 text-foreground/60">
    Events will appear here when an agent attempts a governed action.
  </p>
</div>
```

## Tailwind Utility Guidance

Use these utilities repeatedly:

```tsx
"bg-background text-foreground font-body"
"font-display font-medium leading-[1.05] tracking-tight"
"text-foreground/70"
"text-foreground/55"
"text-xs uppercase tracking-[0.2em] text-foreground/45"
"border border-foreground/15"
"border-b border-foreground/15"
"grid gap-px bg-foreground/15"
"transition-colors duration-300 ease-out"
"focus-visible:ring-2 focus-visible:ring-foreground/90"
```

Avoid these old-platform patterns:

```tsx
"bg-muted/30"
"bg-white"
"rounded-lg"
"shadow-sm"
"text-sky-*"
"text-indigo-*"
"bg-emerald-50"
"border-emerald-200"
```

Replace semantic colors with Ophanix semantic tokens:

| Current light SaaS class | Replacement |
| --- | --- |
| `text-primary` where primary is blue | `text-foreground` or `text-[hsl(var(--accent-teal))]` |
| `bg-primary text-primary-foreground` | `bg-foreground text-background` |
| `hover:bg-accent` | `hover:bg-foreground/5` or `hover:bg-foreground hover:text-background` |
| `bg-muted` | `bg-foreground/5` |
| `text-muted-foreground` | `text-foreground/55` |
| `border` | `border border-foreground/15` |

## Recommended Component Architecture

### Token Layer

Files:

- `src/styles/globals.css`
- `tailwind.config.ts`

Responsibilities:

- Define Ophanix CSS variables.
- Register Sagittaire and PolySans.
- Set body background, foreground, font smoothing, and focus styles.
- Extend Tailwind fonts and semantic accent colors.

### Primitive Layer

Files:

- `src/components/ui/button.tsx`
- `src/components/ui/card.tsx`
- `src/components/ui/input.tsx`
- `src/components/ui/dialog.tsx`
- `src/components/ui/badge.tsx`
- `src/components/ui/table.tsx`

Responsibilities:

- Enforce rectangular geometry.
- Remove default shadows.
- Apply Ophanix text, border, hover, and focus states.
- Keep existing APIs stable.

### Layout Layer

Files:

- `src/components/layout/AppShell.tsx`
- `src/components/layout/SidebarNav.tsx`
- `src/components/layout/TopBar.tsx`
- `src/components/layout/PageHeader.tsx`

Responsibilities:

- Apply dark shell.
- Add logo and brand typography.
- Convert nav to uppercase tracked labels.
- Use active cream fill/navy text.
- Use hairline topbar/sidebar borders.

### Pattern Layer

Add optional shared components:

- `Surface`
- `SectionGrid`
- `MetricGrid`
- `Panel`
- `PageKicker`
- `SegmentedTabs`
- `StatusPill`

Example API:

```tsx
export function SectionGrid({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "grid gap-px border border-foreground/15 bg-foreground/15 [&>*]:bg-background",
        className
      )}
      {...props}
    />
  );
}
```

### Feature Layer

Feature pages should import primitives and patterns, not repeat raw styling. Refactor one page family at a time:

1. Overview
2. Tool decisions/runtime
3. Policies
4. Agents/discovery
5. Trust/mesh
6. MCP/marketplace
7. Compliance/observability

## Refactor Sequence

1. Copy site fonts and logo assets into `packages/product-platform/frontend/public`.
2. Update `src/styles/globals.css` with Ophanix tokens, fonts, body, selection, and focus styles.
3. Update `tailwind.config.ts` with `fontFamily.display`, `fontFamily.body`, and semantic accent colors.
4. Restyle primitives without changing their TypeScript APIs.
5. Restyle `AppShell`, `SidebarNav`, `TopBar`, and `PageHeader`.
6. Create reusable grid/surface patterns.
7. Migrate feature pages from generic light utility classes to Ophanix patterns.
8. Run visual checks at desktop, tablet, and mobile widths.
9. Run `npm run lint`, `npm run typecheck`, and `npm test`.

## Acceptance Criteria

The platform refactor is successful when:

- No white/light gray global surfaces remain.
- Body font is PolySans and high-level headings use Sagittaire.
- Primary actions use cream/navy inversion.
- Borders are cream hairlines with opacity.
- Cards and tables are flat, square, and shadowless by default.
- Status colors use teal, warm orange, and rose rather than Tailwind emerald/amber/rose light backgrounds.
- Sidebar and topbar feel like part of the Ophanix site.
- Dense workflows remain usable and scannable.
- Mobile layouts do not overflow except intentional table scroll regions.
- Focus states are visible and cream-colored.
- Reduced motion users do not receive shader or marquee animation loops.

