# Word default styles the builder emits

Source: `styles.xml` and `theme1.xml` from a document saved by current Microsoft 365 Word (Office 2023 theme, Aptos). Normal body size is 12pt per Microsoft's 2023 theme announcement; earlier 2023 builds shipped 11pt. Units: sizes in points, spacing in points, line spacing as a multiple.

## Theme

| Slot | Value |
|---|---|
| Body font (minor) | Aptos |
| Heading font (major) | Aptos Display |
| Monospace (not a theme slot; builder choice) | Consolas |
| text1 / text2 | 000000 / 0E2841 |
| accent1 to accent6 | 156082, E97132, 196B24, 0F9ED5, A02B93, 4EA72E |
| hyperlink / followed | 467886 / 96607D |
| Heading color | 0F4761 (accent1 darker 25%) |
| Muted text (text1 lighter 35%) | 595959 |

## Paragraph styles

| Style | Font | Size | Color | Before / After | Other |
|---|---|---|---|---|---|
| Normal | Aptos | 12 | auto | 0 / 8 | line 1.15 |
| Title | Aptos Display | 28 | auto | 0 / 4 | letter spacing -0.5pt, kern 14pt, single spacing |
| Subtitle | Aptos | 14 | 595959 | 0 / 8 | letter spacing +0.75pt |
| Heading 1 | Aptos Display | 20 | 0F4761 | 18 / 4 | keep with next, keep lines, outline 0 |
| Heading 2 | Aptos Display | 16 | 0F4761 | 8 / 4 | outline 1 |
| Heading 3 | Aptos | 14 | 0F4761 | 8 / 4 | outline 2 |
| Heading 4 | Aptos | 12 italic | 0F4761 | 4 / 2 | outline 3 |
| Heading 5 | Aptos | 12 | 0F4761 | 4 / 2 | outline 4 |
| Heading 6 | Aptos | 12 italic | 595959 | 2 / 0 | outline 5 |
| Quote | Aptos | 12 italic | 404040 | 8 / 8 | indented 0.5in both sides (Word centers; builder indents for readability) |
| Caption | Aptos | 9 italic | 0E2841 | 0 / 10 | centered under figures |
| List Paragraph | Aptos | 12 | auto | 0 / 8 | left indent 0.5in, contextual spacing |
| Code Block (custom) | Consolas | 9.5 | auto | 0 / 0 | shaded F2F2F2, single spacing |
| Header Text (custom) | Aptos | 9 | 595959 | 0 / 0 | header and footer lines |

Character styles: Hyperlink (467886, underlined), Code Char (Consolas 10pt, shaded F2F2F2).

## Page

| Setting | Value |
|---|---|
| Size | US Letter 8.5x11in (`page: a4` for 210x297mm) |
| Margins | 1in all sides; header and footer at 0.5in |
| Text width | 6.5in (9360 DXA); figures scale to fit |
| Header (pages 2+) | title left, "Author  \|  Month D, YYYY" right, 9pt muted |
| Footer | optional text left, "Page X of Y" right |
| First page | title block: Title, Subtitle, byline "Author  \|  date  \|  status" |
| File properties | creator and last modified by = author; title, subject = subtitle |

## Lists and tables

- Bullets: •, ◦, ▪ at 0.5in, 1.0in, 1.5in with 0.25in hanging indent.
- Numbers: 1., a., i. with the same indents. Each top-level list restarts at 1.
- Tables: full text width, 0.5pt black grid, header row bold on F2F2F2, cell padding 3pt vertical 5pt horizontal, single spacing in cells, rows do not split across pages.
