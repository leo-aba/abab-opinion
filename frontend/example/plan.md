# Plan: AI Video Opinion Analytics Platform — Frontend Prototype

**Generated**: 2026-06-29
**Estimated Complexity**: High
**Tech Stack**: Pure HTML5 + CSS3 + JavaScript (Chart.js CDN for charts)

## Overview

Build a modern AI SaaS-style frontend prototype for an AI-powered video comment analysis platform. The prototype covers the full user journey: Login → Dashboard → Create Analysis (Wizard) → Real-time Analysis → Results. Design follows a minimal, tech-forward aesthetic inspired by OpenAI, Notion, Linear, and Vercel.

**Design System** (from requirements doc):
- Background: `#F5F6F8` | Surface: `#FFFFFF` | Text: `#222222` | Sub-text: `#666666`
- Border: `#E5E7EB` | Hover: `#F0F2F5` | Accent: `#3B82F6`
- Animations: Fade, Slide, Scale, Blur — no rotation/bounce/particles
- Icons: SVG inline (Lucide-style minimal icons)

## Page Structure

```
Login → Dashboard → ├── Home (stats + charts)
                     ├── Create Analysis (4-step wizard)
                     ├── Real-time Analysis (pipeline)
                     ├── Results (tabs: Overview, Topics, Sentiment, Trends, AI Summary)
                     ├── Video Management (Netflix-style grid)
                     ├── History (table)
                     └── Settings
```

---

## Sprint 1: Foundation — Login Page

**Goal**: Landing page with left-right split, blur circles, login form with animations
**Demo**: Open index.html → see login page → enter credentials → fade transition to dashboard

### Task 1.1: Create HTML shell with CSS design tokens
- **Location**: `E:\pycharm\ababOpinion\frontend\example\index.html`
- **Description**: Set up HTML5 boilerplate, CSS custom properties, Google Fonts (Inter), Chart.js CDN
- **Acceptance Criteria**: CSS variables defined for all design tokens; Inter font loaded
- **Validation**: Open in browser, inspect CSS variables in devtools

### Task 1.2: Build Login page layout
- **Description**: Left-right split (60/40), left side has logo, tagline, feature bullets, blur circle decorations; right side has login card
- **Acceptance Criteria**: Layout matches spec; blur circles render correctly; responsive down to tablet
- **Validation**: Visual comparison with spec

### Task 1.3: Add login form and animations
- **Description**: Username/password inputs, login/register/forgot-password buttons; button hover shadow expansion + gradient; page fade-out on submit
- **Acceptance Criteria**: Hover animation 0.25s; submit triggers fade-out → dashboard fade-in transition

---

## Sprint 2: Dashboard Shell + Home

**Goal**: Sidebar layout, stat cards, charts on dashboard home
**Demo**: Login → Dashboard; see sidebar nav, stat cards, trend chart, pie chart, topic bar chart

### Task 2.1: Build sidebar + header layout
- **Description**: Fixed left sidebar (240px) with logo, nav items (Dashboard, Data Analysis, Video Mgmt, History, Settings), user avatar + logout at bottom. Top header bar with welcome message and quick stats
- **Acceptance Criteria**: Sidebar fixed; nav items highlight active; header shows dynamic greeting
- **Validation**: Click nav items → active state changes

### Task 2.2: Build StatCard components (4 cards)
- **Description**: Comment count (123,221 ↑12%), Video count (421), Hot Topic (AI), Avg Sentiment (Positive). Each card: icon, label, value, trend indicator. Hover: scale(1.02) + shadow lift
- **Acceptance Criteria**: All 4 cards render; hover animation works; trend arrow colors correct
- **Validation**: Hover each card → visual lift effect

### Task 2.3: Build chart cards (Trend + Pie + Bar)
- **Description**: Line chart (comment growth trend), Pie/Donut chart (sentiment distribution), Horizontal bar chart (TOP10 topics). Use Chart.js with custom styling matching design tokens
- **Acceptance Criteria**: All 3 charts render with mock data; responsive resize; tooltips work
- **Validation**: Hover chart data points → tooltips appear

---

## Sprint 3: Create Analysis Wizard

**Goal**: 4-step wizard flow with step indicator, platform cards, video search, parameter config
**Demo**: Click "Create Analysis" → walk through 4 steps → reach real-time analysis

### Task 3.1: Build wizard step indicator + Step 1 (Platform select)
- **Description**: Horizontal step indicator (4 steps) at top. Step 1: Two platform cards (Bilibili, Douyin) with logo, name, checkmark on select. Hover: scale + blue border + shadow
- **Acceptance Criteria**: Step indicator shows current step; platform cards selectable; selected state visible
- **Validation**: Click platform card → checkmark appears, blue border

### Task 3.2: Build Step 2 (Video search)
- **Description**: Tabbed input (URL / BV号 / AV号 / Keyword search). Search results table with: cover thumbnail, title, uploader, publish date, comment count, "Select" button
- **Acceptance Criteria**: Input tabs switch; search triggers results display (mock data); select button works
- **Validation**: Type keyword → results appear; click Select → advances

### Task 3.3: Build Step 3 (Analysis parameters)
- **Description**: Comment count selector (100/500/1000/5000/All), Time range (7d/30d/All), Language (Chinese/English/All). Card-style selectors
- **Acceptance Criteria**: All parameter groups render; selections highlight; validation before next
- **Validation**: Select params → click Next → advances to Step 4

### Task 3.4: Build Step 4 (Start Analysis)
- **Description**: Summary of selections + large "Start Analysis" button → transitions to real-time analysis page
- **Acceptance Criteria**: Summary shows all selections; button click → pipeline page with transition

---

## Sprint 4: Real-time Analysis Page

**Goal**: Pipeline visualization with step status, progress bar, scrolling logs
**Demo**: See pipeline animate through steps, progress bar fill, logs scroll

### Task 4.1: Build pipeline component
- **Description**: Vertical pipeline: Comment Collection → Data Cleaning → Embedding → Clustering → Topic Generation → Summary. Each step: icon + label + status (done=green check, running=blue spinner, waiting=gray). CI/CD pipeline aesthetic
- **Acceptance Criteria**: Steps animate sequentially; status colors correct; pipeline visual flow clear
- **Validation**: Watch pipeline auto-advance through mock steps

### Task 4.2: Build progress bar + log panel
- **Description**: Top progress bar (% + fill). Right-side log panel with timestamped entries, auto-scrolling. Monospace font, terminal-like appearance
- **Acceptance Criteria**: Progress bar fills smoothly; logs appear sequentially; auto-scroll to bottom
- **Validation**: Observe progress + logs advancing together

---

## Sprint 5: Analysis Results Pages

**Goal**: Tabbed results with Overview, Topics, Sentiment, Trends, AI Summary, Smart Comment Search
**Demo**: Pipeline completes → results load; browse all tabs

### Task 5.1: Build Overview tab
- **Description**: Summary stats (total comments, topics, sentiment distribution 72%/18%/10%), key insights cards
- **Acceptance Criteria**: All stats render; sentiment distribution clear

### Task 5.2: Build Topic clustering tab
- **Description**: Left: topic list (ranked by comment count). Right: topic detail panel with representative comments, keywords, AI summary. Click topic → right panel updates
- **Acceptance Criteria**: Topic list clickable; detail panel shows relevant data

### Task 5.3: Build Sentiment analysis tab
- **Description**: Sunburst chart + Pie chart + Radar chart showing sentiment by topic (AI→Positive, Price→Negative, Performance→Positive, Battery→Mixed)
- **Acceptance Criteria**: Multiple chart types render; data coherent across charts

### Task 5.4: Build Trends + AI Summary tabs
- **Description**: Trends: line chart with day/hour/week toggle. AI Summary: rich text summary card with key findings, generated at timestamp
- **Acceptance Criteria**: Time granularity toggle works; AI summary styled as rich card

### Task 5.5: Build Smart Comment Search
- **Description**: Search box in results page, input keyword → filter comments with topic + vector relevance, highlight matched terms
- **Acceptance Criteria**: Search filters comments in real-time; highlights visible

---

## Sprint 6: Video Management + History

**Goal**: Netflix-style video grid and history data table
**Demo**: Browse managed videos, view history records

### Task 6.1: Build Video Management grid
- **Description**: Card grid (3-4 columns). Each card: cover image, title, platform badge, date, comment count, last analysis time, status badge. Netflix-style hover: scale + info overlay
- **Acceptance Criteria**: Grid responsive; hover effect works; status badges correct colors

### Task 6.2: Build History table
- **Description**: Sortable data table: video, platform, topic count, comment count, analysis time, "View" action. Filter by platform, date range. Pagination
- **Acceptance Criteria**: Table sortable; filters work; pagination functional

---

## Sprint 7: Integration & Polish

**Goal**: Wire all pages, global navigation, smooth transitions, final polish
**Demo**: Full user journey from login to results, all transitions smooth

### Task 7.1: Implement SPA routing
- **Description**: Hash-based routing (`#login`, `#dashboard`, `#wizard`, `#pipeline`, `#results`, `#videos`, `#history`, `#settings`). Page transitions with CSS fade/slide
- **Acceptance Criteria**: All routes work; browser back/forward functional; transitions smooth

### Task 7.2: Global state + polish
- **Description**: Active nav state, page entrance animations, skeleton loading states, responsive breakpoints (mobile sidebar collapse), accessibility (focus rings, aria labels, keyboard nav)
- **Acceptance Criteria**: All states handled; mobile responsive; animations consistent

---

## Testing Strategy

- **Visual**: Compare each page against requirements doc specifications
- **Interaction**: Test all clickable elements, hover states, transitions
- **Responsive**: Test at 375px, 768px, 1024px, 1440px widths
- **Animation**: Verify all transitions are smooth, no jank, all respect reduced-motion

## Potential Risks & Gotchas

| Risk | Mitigation |
|------|------------|
| Chart.js theming conflicts with design tokens | Override Chart.js defaults with custom plugin/config |
| Large single HTML file hard to maintain | Clear section comments; component-based CSS organization |
| Mobile sidebar UX | Hamburger toggle + overlay on mobile; sidebar fixed on desktop |
| Animation performance | Use transform/opacity only; avoid animating layout properties |
| Mock data realism | Generate diverse, realistic Chinese video/comment mock data |
