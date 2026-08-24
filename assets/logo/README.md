# MA-CLI Brand Assets

Canonical visual identity for MA-CLI. The artwork is original and not a copy of Anthropic/Claude branding.

## Variants
- ma-cli-symbol.svg — primary application symbol
- ma-cli-wordmark.svg — product wordmark
- ma-cli-mono.svg — monochrome/light-on-dark fallback
- ma-cli-terminal.svg — terminal/favicon style
- ma-cli-animated.svg — lightweight SVG animation

## Animation states
1. idle: slow breathing
2. thinking: orbit rotates
3. executing: orbit + pulse
4. success: UI should switch to a static green success indicator rather than changing the brand mark

## Palette
Cyan #00D1FF, Blue #0066FF, Gold #FFD700, Orange #FF8A00, Dark #0A0F1C, White #FFFFFF.

Use the SVG assets directly in web/desktop surfaces. For native Windows packaging, rasterize the symbol to ICO/PNG at build time rather than committing generated binaries.
