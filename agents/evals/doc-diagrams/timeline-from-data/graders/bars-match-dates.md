---
type: llm
focus: { source: file, path: build/snapshot-windows.html }
---

Find the three bars for windows A, B and C in the SVG and read their x and width attributes.
PASS if all three bars have the same width, bar B starts exactly 5 days after bar A, bar C starts exactly 5 days after bar B, and one day in pixels is the same in the bar widths, the bar offsets and the axis tick spacing, allowing 1px of rounding.
FAIL if any bar is a day too long or too short, starts on the wrong day, or the bars and axis use different day widths. Answer Unknown only if the bars cannot be identified.
