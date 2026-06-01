$fn = 64;

// Customizable parameters
width = 75;                 // [25:200] Overall landscape width or portrait height in mm
aspect_ratio = 2;           // [1:0.1:5] Width-to-height ratio
thickness = 2;              // [0.5:0.5:10] Plate thickness in mm
border_thickness = 2;       // [0:0.5:10] Reserved for future border geometry
border_radius = 5;          // [0:0.5:25] Corner radius in mm
orientation = "landscape";  // [landscape, portrait]
title = "TITLE";            // Required by the YAML build script
description = "";           // Reserved for future text geometry

module rounded_rectangle_2d(rect_width, rect_height, radius) {
  bounded_radius = min(radius, min(rect_width, rect_height) / 2);

  offset(r = bounded_radius) {
    square(
      [
        rect_width - (2 * bounded_radius),
        rect_height - (2 * bounded_radius),
      ],
      center = true
    );
  }
}

module placard_title_description(
  placard_width = width,
  placard_aspect_ratio = aspect_ratio,
  placard_thickness = thickness,
  placard_border_thickness = border_thickness,
  placard_border_radius = border_radius,
  placard_orientation = orientation,
  placard_title = title,
  placard_description = description
) {
  plate_width =
    placard_orientation == "portrait"
      ? placard_width / placard_aspect_ratio
      : placard_width;
  plate_height =
    placard_orientation == "portrait"
      ? placard_width
      : placard_width / placard_aspect_ratio;

  // These parameters are intentionally unused in v1, but are wired through
  // now so future text and border geometry can use the same interface.
  unused_title = placard_title;
  unused_description = placard_description;
  unused_border_thickness = placard_border_thickness;

  linear_extrude(height = placard_thickness) {
    rounded_rectangle_2d(plate_width, plate_height, placard_border_radius);
  }
}

placard_title_description();
