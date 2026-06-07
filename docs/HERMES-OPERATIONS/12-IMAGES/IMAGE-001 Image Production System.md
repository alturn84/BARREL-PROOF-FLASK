# IMAGE-001 — Image Production System

## Game of the Day Image Standards
- AI generates artwork only
- No logos, player names, team names, or uniform numbers
- Team colors only
- Vintage newspaper aesthetic

## Dynamic Overlays (rendered separately)
- Score
- Team abbreviations
- Headline
- Date

## Standard Image Sizes
| Use | Dimensions | Ratio |
|-----|-----------|-------|
| Page banners | 1774 x 887 | 2:1 |
| Game of the Day | TBD | 3:2 |
| Social cards | 1600 x 900 | 16:9 |
| Archive thumbnails | 1200 x 630 | ~1.9:1 |

## Architecture Principle
Separate artwork generation from daily text rendering.
Artwork is generated once per game. Overlays are rendered at publish time.

## Status
FOUNDATION ONLY — implementation pending.
