# Placard Title Description Model

Reusable OpenSCAD model for a rounded placard with title and description values.

The model uses the substrate model as a thin backing, then raises a border,
clipped title, and wrapped description to the requested total thickness. Title
and description alignment can be set independently. Description line spacing is
controlled with the `description_line_height` multiplier.

The build also emits a two-object `placard.3mf`: the backing plus raised
title-description features use `text_color`, and the full-height substrate is
cut with a boolean difference and uses `substrate_color`. Colors are written as
3MF Materials Extension color groups for slicers such as Bambu Studio and
OrcaSlicer.

## Commands

```bash
moon run placard-title-description:build
moon run placard-title-description:verify
moon run placard-title-description:package
```
