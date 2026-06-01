# Placard Title Description Model

Reusable OpenSCAD model for a rounded placard with title, description, and an
optional QR code value.

The model uses the substrate model as a thin backing, then raises a border,
clipped title, and wrapped description to the requested total thickness. Title
and description alignment can be set independently. Description line spacing is
controlled with the `description_line_height` multiplier, and description
vertical alignment supports `top`, `center`, and `bottom`. When `qr_code` is
set, the build uses the Python `segno` package, managed by `uv`, to encode the
exact string, reserves a square QR area on the right side of the description
block, and wraps the description in the remaining width.

The build emits a two-object `placard.3mf` by default: the backing plus raised
title-description features use `text_color`, and the full-height substrate is
cut with a boolean difference and uses `substrate_color`. With `qr_code`, the
3MF also contains fixed-color `qr-background` (`#FFFFFF`) and `qr-dots`
(`#000000`) objects. Colors are written as 3MF Materials Extension color groups
for slicers such as Bambu Studio and OrcaSlicer.

## Commands

```bash
moon run placard-title-description:build
moon run placard-title-description:verify
moon run placard-title-description:package
```
