# Nanobots TMA — Design System

Extracted from pencil-new.pen. All values are pixel-perfect from the design tool.

## Color Palette

### Backgrounds
- `--bg`: #0C0C0C (page)
- `--bg-card`: #1A1A1A (cards, elevated surfaces)
- `--bg-elevated`: #242424 (nested elements inside cards)

### Text
- `--text`: #FFFFFF (primary)
- `--text-2`: #8A8A8A (secondary)
- `--text-3`: #525252 (muted/dim)
- `--text-4`: #3A3A3A (separator characters)
- `--text-5`: #2A2A2A (very dim, chevrons)

### Accent Colors (from logo)
- `--orange`: #FF9F1C (primary accent — from logo triangle)
- `--purple`: #7B6CDB (secondary accent — from logo circle)
- `--green`: #32D74B (success, online)
- `--yellow`: #FFB547 (warning, tertiary accent)

### Accent Variants (opacity)
- `--orange-15`: #FF9F1C15
- `--orange-20`: #FF9F1C20
- `--orange-40`: #FF9F1C40
- `--orange-66`: #FF9F1C66
- `--purple-12`: #7B6CDB12
- `--purple-20`: #7B6CDB20
- `--green-12`: #32D74B12
- `--green-15`: #32D74B15
- `--green-20`: #32D74B20

### Borders
- `--border`: #2A2A2A (default)
- `--border-hero`: #2A2A4A (hero card gradient border)
- `--border-light`: #FFFFFF18 (subtle on mesh gradient cards)

### Overlays
- `--overlay`: #00000080 (bottom sheet backdrop)
- `--white-08`: #FFFFFF08 (very subtle tint)
- `--white-10`: #FFFFFF10 (dividers in hero cards)
- `--white-15`: #FFFFFF15 (buttons in hero cards)
- `--white-50`: #FFFFFF50 (meta text on mesh gradients)
- `--white-60`: #FFFFFF60 (body text on hero agents)

## Typography

### Font Families
- **Sora** — Headlines, device names, section titles (geometric, bold)
- **Inter** — Body text, labels, meta, badges (clean sans-serif)

### Type Scale
| Size | Weight | Font | Usage |
|------|--------|------|-------|
| 28px | 700 | Sora | Page title ("Files") - letterSpacing: -1 |
| 24px | 700 | Sora | Main title ("Command Center") - letterSpacing: -1 |
| 22px | 700 | Sora | Hero device name - letterSpacing: -0.5 |
| 20px | 700 | Sora | Screen header ("MacBook Pro") - letterSpacing: -0.5 |
| 18px | 700 | Sora | Section title / path ("~/Desktop") - letterSpacing: -0.5 |
| 16px | 700 | Sora | Card title / device name - letterSpacing: -0.3 |
| 16px | 700 | Sora | Status bar time - letterSpacing: -0.5 |
| 15px | 600 | Inter | Project name in list |
| 14px | 700 | Sora | Section label ("Agents", "Files") - letterSpacing: -0.3 |
| 14px | 600 | Inter | Agent name, file row name |
| 14px | 400 | Inter | Chat message body, input text |
| 13px | 600 | Inter | File name, agent name in chip |
| 13px | 500 | Inter | Breadcrumb, meta |
| 12px | 600 | Inter | Agent chip name, drive name, project name mono |
| 12px | 500 | Inter | Pill selector text |
| 11px | 400 | Inter | Meta text (macOS · Online · 8h uptime) |
| 11px | 600 | Inter | Agent task text |
| 10px | 700 | Inter | Section label uppercase (DEVICES, KEY FILES) - letterSpacing: 1.5 |
| 10px | 500 | Inter | Drive size text |
| 9px | 700 | Inter | Badge text (ONLINE, RELAY, OS) - letterSpacing: 0.5-1 |

## Spacing

### Gap (between elements)
- 40px — major section (splash screen)
- 20px — section gap (scroll content), header gap (back → text)
- 16px — section content gap, file area gap
- 14px — header row gap, card content gap
- 12px — card internal gap, agent list gap
- 10px — card row gap, file row gap, mini card gap
- 8px — tight gap (chip row, agent card internal, drive list)
- 6px — drive row gap, badge internal
- 5px — badge dot + text
- 4px — tight label stack, progress bar to text
- 3px — name + meta stack
- 2px — title + breadcrumb stack
- 1px — name + subtitle in drive

### Padding
- `[24, 24, 0, 24]` — section wrapper (top:24, sides:24)
- `[20, 24, 0, 24]` — title wrapper
- `[16, 24]` — scroll content area
- `[8, 24, 0, 16]` — header with back button
- `[8, 24, 24, 24]` — bottom nav wrapper
- `[20, 20, 16, 20]` — hero card
- `[14, 16]` — card row (file row, drive row)
- `[12, 14]` — compact card (agent row, activity row, drive)
- `[10, 12]` — agent inline row
- `[8, 14]` — pill selector
- `[8, 12]` — agent chip
- `[6, 10]` — relay badge
- `[4, 10]` — online badge, status badge
- `[3, 8]` — status pill
- `[1, 5]` — OS micro badge
- `[14, 32]` — CTA button ("Get Started")

## Corner Radius
- 20px — bottom sheet top corners
- 16px — hero card, large bento cards, bottom nav pill
- 14px — chat bubbles (with 4px on tail corner)
- 12px — standard cards, buttons, agent cards, drive cards
- 10px — compact cards, inputs, back button, file rows
- 8px — icon containers, avatar frames, mini buttons, chips
- 7px — agent avatar (slightly smaller)
- 6px — badge pills, status badges, agent avatars (small), tool card
- 5px — agent number badge on files
- 4px — micro badges (OS)
- 3px — badge radius (count)
- 2px — progress bars, handle bar

## Component Patterns

### Bottom Nav (CHAT / DEVICE / MORE)
- Container: fill width, height 56px, padding 4px, bg #1A1A1A, radius 16px, border #2A2A2A
- Tab item: fill_container width, fill height, vertical layout, center, gap 4px, radius 12px
- Active tab: bg orange-15 (#FF9F1C15)
- Active icon: #FF9F1C, Active text: #FF9F1C, fontSize 9, weight 700, letterSpacing 1
- Inactive icon: #525252, Inactive text: #525252, fontSize 9, weight 600
- Nav wrapper padding: [8, 24, 24, 24]

### Header (with back button)
- Container: fill width, padding [8, 24, 0, 16], horizontal, alignItems center, gap 20
- Back button: 36×36, bg #1A1A1A, radius 8, chevron-left icon #FF9F1C 18px
- Title: Sora 20px 700 #FFFFFF letterSpacing -0.5
- Meta: Inter 11px normal #525252
- ONLINE badge: horizontal, gap 5, padding [4,10], bg #32D74B15, radius 6, dot 6×6 #32D74B, text "ONLINE" Inter 9px 700 #32D74B

### Hero Device Card (Hub)
- Gradient fill: linear 160° [#1A1A2E → #16213E → #0F3460]
- Border: #2A2A4A 1px
- Shadow: y:8 blur:32 #00000060
- Radius: 16px
- Padding: [20, 20, 16, 20]
- ONLINE badge: bg #32D74B20, radius 4, Inter 9px 700 #32D74B
- Device icon: 48×48, bg #FFFFFF10, radius 14, laptop icon 24px #FFFFFF
- Agent rows inside: bg #FFFFFF08, radius 8, padding [8,12], gap 10
- Agent avatar: 24×24, radius 6, colored fill, bot icon 12px white
- Status dot: 8×8, colored with glow shadow

### Bento File Cards (Device screen)
- Large cards: 172×172, radius 16, mesh_gradient fill, border #FFFFFF18
- Compact cards: 172×80, radius 12, bg #1A1A1A, border #FFFFFF18
- Icon: 26px on large, 20px on compact
- Name: Sora 16px 700 on large, Inter 13px 600 on compact
- Meta: Inter 11px #FFFFFF50 on large, Inter 10px #525252 on compact

### Drive Row
- Container: fill width, horizontal, padding [12,14], gap 12, bg #1A1A1A, radius 10, border #2A2A2A
- Name: Sora 14px 700 #FFFFFF
- Size text: Inter 10px #525252
- Progress bar: fill width, height 4px, bg #FFFFFF08, radius 2, fill colored
- Chevron: 16px #2A2A2A
- System drive: border purple-20, OS badge (purple bg, "OS" text)
- Warning drive: name + size in orange, bar in orange

### Chat Bubbles
- User: right-aligned, gradient bg [#1A1A2E → #16213E], radius [16,16,4,16], border #2A2A4A
- Agent: left-aligned, bg #1A1A1A, radius [16,16,16,4], border #2A2A2A
- Agent label: avatar 20×20 colored radius 6, name Inter 11px 600 colored, time Inter 10px #525252

### Bottom Sheet
- Background: #0C0C0C
- Top corners: radius 20px
- Border: top+left+right #2A2A2A
- Handle: 36×4 #2A2A2A radius 2, padding [12,0,6,0]
- Title: Sora 18px 700 #FFFFFF letterSpacing -0.5
- Close button: 30×30 bg #1A1A1A radius 8, X icon 16px #525252

## Screen List

1. **Splash (20)** — Logo centered, tagline, "Get Started" orange button
2. **Hub (11)** — Command Center, hero device card with expandable agents, other devices grid, activity feed
3. **Device (14)** — MacBook Pro header, agents list, bento file grid (Projects+Documents large, Desktop+Downloads compact), drives
4. **Chat (15)** — Full screen, no bottom nav. Header: back + "Chat" + breadcrumb. Switch context button top-right
5. **Switch Context (17)** — Bottom sheet over chat. Pill selectors (device ▾, agent ▾) + project list
6. **Project (18)** — Header with history button, horizontal agent chips, key files with agent badges, regular files, browse all
7. **Recent Changes (19)** — Bottom sheet popup, file change history per agent
8. **File List (8)** — Path header, file rows with colored icons
9. **More (9)** — Settings groups (Workspace, System)

## Navigation

- Bottom nav: CHAT / DEVICE / MORE (on Device, More, File List screens)
- Chat: full screen, no bottom nav
- Back arrow → returns to previous screen
- Hub: no bottom nav, accessed via back from Device/Chat/More

## Icons

All from **Lucide** icon set:
- Navigation: chevron-left, chevron-right, chevron-down, arrow-right, arrow-up, x
- Devices: laptop, monitor
- Files: folder, folder-kanban, folder-open, file-text, file-code, download
- Actions: plus, check, repeat, settings, bot, sparkles, terminal, pin
- Status: loader, git-commit-horizontal, ban
- Layout: layout-dashboard, message-circle, hard-drive
