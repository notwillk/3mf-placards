$fn = 64;

use <../substrate/model.scad>;

// Customizable parameters
width = 75;                    // [25:200] Overall landscape width or portrait height in mm
aspect_ratio = 2;              // [1:0.1:5] Width-to-height ratio
thickness = 2;                 // [0.5:0.5:10] Total placard thickness in mm
backing_thickness = 0.4;       // [0.1:0.1:5] Backing thickness in mm
border_thickness = 2;          // [0:0.5:10] Raised border stroke width in mm
border_radius = 5;             // [0:0.5:25] Corner radius in mm
orientation = "landscape";     // [landscape, portrait]
padding = 2;                   // [0:0.5:20] Space between border and text in mm
gap = 1;                       // [0:0.5:20] Space between title and description in mm
title = "TITLE";               // Required by the YAML build script
title_typeface = "";           // Empty uses OpenSCAD's default font
title_size = 6;                // [1:0.5:30] Title text size in mm
title_alignment = "center";    // [left, center, right]
description = "";              // Optional description text
description_typeface = "";     // Empty uses OpenSCAD's default font
description_size = 6;          // [1:0.5:30] Description text size in mm
description_alignment = "center"; // [left, center, right]
description_lines = [];        // Generated wrapped description lines
description_line_height = 1.25; // [0.5:0.05:3] Description line height multiplier
description_line_spacing = description_size * description_line_height; // Generated from description line height
title_block_height_factor = 1.25; // Descender-safe title layout factor
text_color = "#000000";         // Text and raised border color
substrate_color = "#FFFFFF";    // Substrate color

function text_anchor_x(alignment, plate_width, text_inset) =
  alignment == "left"
    ? (-plate_width / 2) + text_inset
    : alignment == "right"
      ? (plate_width / 2) - text_inset
      : 0;

module raised_border_2d(plate_width, plate_height, radius, border_width) {
  if (border_width > 0) {
    difference() {
      rounded_rectangle_2d(plate_width, plate_height, radius);
      rounded_rectangle_2d(
        plate_width - (2 * border_width),
        plate_height - (2 * border_width),
        max(0, radius - border_width)
      );
    }
  }
}

module placard_text_2d(
  label,
  text_size,
  text_typeface = "",
  text_halign = "center",
  text_valign = "top"
) {
  if (text_typeface == "") {
    text(label, size = text_size, halign = text_halign, valign = text_valign);
  } else {
    text(
      label,
      size = text_size,
      font = text_typeface,
      halign = text_halign,
      valign = text_valign
    );
  }
}

module clipped_title_2d(
  label,
  text_size,
  text_typeface,
  text_alignment,
  text_x,
  text_y,
  clip_width,
  clip_height
) {
  intersection() {
    translate([text_x, text_y]) {
      placard_text_2d(
        label,
        text_size,
        text_typeface,
        text_alignment,
        "top"
      );
    }

    translate([0, text_y - (clip_height / 2)]) {
      square([clip_width, clip_height], center = true);
    }
  }
}

module placard_title_description_features(
  placard_width = width,
  placard_aspect_ratio = aspect_ratio,
  placard_thickness = thickness,
  placard_backing_thickness = backing_thickness,
  placard_border_thickness = border_thickness,
  placard_border_radius = border_radius,
  placard_orientation = orientation,
  placard_padding = padding,
  placard_gap = gap,
  placard_title = title,
  placard_title_typeface = title_typeface,
  placard_title_size = title_size,
  placard_title_block_height_factor = title_block_height_factor,
  placard_title_alignment = title_alignment,
  placard_description = description,
  placard_description_typeface = description_typeface,
  placard_description_size = description_size,
  placard_description_alignment = description_alignment,
  placard_description_lines = description_lines,
  placard_description_line_spacing = description_line_spacing
) {
  plate_width = substrate_plate_width(
    placard_width,
    placard_aspect_ratio,
    placard_orientation
  );
  plate_height = substrate_plate_height(
    placard_width,
    placard_aspect_ratio,
    placard_orientation
  );
  feature_thickness = placard_thickness - placard_backing_thickness;
  feature_overlap = min(0.01, placard_backing_thickness / 2);
  text_inset = placard_border_thickness + placard_padding;
  text_area_width = plate_width - (2 * text_inset);
  text_area_top = (plate_height / 2) - text_inset;
  title_x = text_anchor_x(
    placard_title_alignment,
    plate_width,
    text_inset
  );
  description_x = text_anchor_x(
    placard_description_alignment,
    plate_width,
    text_inset
  );
  title_block_height = placard_title_size * placard_title_block_height_factor;
  description_top = text_area_top - title_block_height - placard_gap;

  translate([0, 0, placard_backing_thickness - feature_overlap]) {
    linear_extrude(height = feature_thickness + feature_overlap) {
      union() {
        raised_border_2d(
          plate_width,
          plate_height,
          placard_border_radius,
          placard_border_thickness
        );

        clipped_title_2d(
          placard_title,
          placard_title_size,
          placard_title_typeface,
          placard_title_alignment,
          title_x,
          text_area_top,
          text_area_width,
          title_block_height
        );

        if (len(placard_description_lines) > 0) {
          for (line_index = [0 : len(placard_description_lines) - 1]) {
            translate(
              [
                description_x,
                description_top -
                  (line_index * placard_description_line_spacing),
              ]
            ) {
              placard_text_2d(
                placard_description_lines[line_index],
                placard_description_size,
                placard_description_typeface,
                placard_description_alignment,
                "top"
              );
            }
          }
        }
      }
    }
  }
}

module placard_title_description_body(
  placard_width = width,
  placard_aspect_ratio = aspect_ratio,
  placard_thickness = thickness,
  placard_backing_thickness = backing_thickness,
  placard_border_thickness = border_thickness,
  placard_border_radius = border_radius,
  placard_orientation = orientation,
  placard_padding = padding,
  placard_gap = gap,
  placard_title = title,
  placard_title_typeface = title_typeface,
  placard_title_size = title_size,
  placard_title_block_height_factor = title_block_height_factor,
  placard_title_alignment = title_alignment,
  placard_description = description,
  placard_description_typeface = description_typeface,
  placard_description_size = description_size,
  placard_description_alignment = description_alignment,
  placard_description_lines = description_lines,
  placard_description_line_spacing = description_line_spacing
) {
  union() {
    substrate(
      substrate_width = placard_width,
      substrate_aspect_ratio = placard_aspect_ratio,
      substrate_thickness = placard_backing_thickness,
      substrate_border_radius = placard_border_radius,
      substrate_orientation = placard_orientation
    );

    placard_title_description_features(
      placard_width = placard_width,
      placard_aspect_ratio = placard_aspect_ratio,
      placard_thickness = placard_thickness,
      placard_backing_thickness = placard_backing_thickness,
      placard_border_thickness = placard_border_thickness,
      placard_border_radius = placard_border_radius,
      placard_orientation = placard_orientation,
      placard_padding = placard_padding,
      placard_gap = placard_gap,
      placard_title = placard_title,
      placard_title_typeface = placard_title_typeface,
      placard_title_size = placard_title_size,
      placard_title_block_height_factor = placard_title_block_height_factor,
      placard_title_alignment = placard_title_alignment,
      placard_description = placard_description,
      placard_description_typeface = placard_description_typeface,
      placard_description_size = placard_description_size,
      placard_description_alignment = placard_description_alignment,
      placard_description_lines = placard_description_lines,
      placard_description_line_spacing = placard_description_line_spacing
    );
  }
}

module placard_substrate_cut(
  placard_width = width,
  placard_aspect_ratio = aspect_ratio,
  placard_thickness = thickness,
  placard_backing_thickness = backing_thickness,
  placard_border_thickness = border_thickness,
  placard_border_radius = border_radius,
  placard_orientation = orientation,
  placard_padding = padding,
  placard_gap = gap,
  placard_title = title,
  placard_title_typeface = title_typeface,
  placard_title_size = title_size,
  placard_title_block_height_factor = title_block_height_factor,
  placard_title_alignment = title_alignment,
  placard_description = description,
  placard_description_typeface = description_typeface,
  placard_description_size = description_size,
  placard_description_alignment = description_alignment,
  placard_description_lines = description_lines,
  placard_description_line_spacing = description_line_spacing,
  placard_substrate_color = substrate_color
) {
  color(placard_substrate_color) {
    difference() {
      substrate(
        substrate_width = placard_width,
        substrate_aspect_ratio = placard_aspect_ratio,
        substrate_thickness = placard_thickness,
        substrate_border_radius = placard_border_radius,
        substrate_orientation = placard_orientation
      );

      placard_title_description_body(
        placard_width = placard_width,
        placard_aspect_ratio = placard_aspect_ratio,
        placard_thickness = placard_thickness,
        placard_backing_thickness = placard_backing_thickness,
        placard_border_thickness = placard_border_thickness,
        placard_border_radius = placard_border_radius,
        placard_orientation = placard_orientation,
        placard_padding = placard_padding,
        placard_gap = placard_gap,
        placard_title = placard_title,
        placard_title_typeface = placard_title_typeface,
        placard_title_size = placard_title_size,
        placard_title_block_height_factor = placard_title_block_height_factor,
        placard_title_alignment = placard_title_alignment,
        placard_description = placard_description,
        placard_description_typeface = placard_description_typeface,
        placard_description_size = placard_description_size,
        placard_description_alignment = placard_description_alignment,
        placard_description_lines = placard_description_lines,
        placard_description_line_spacing = placard_description_line_spacing
      );
    }
  }
}

module placard_title_description(
  placard_width = width,
  placard_aspect_ratio = aspect_ratio,
  placard_thickness = thickness,
  placard_backing_thickness = backing_thickness,
  placard_border_thickness = border_thickness,
  placard_border_radius = border_radius,
  placard_orientation = orientation,
  placard_padding = padding,
  placard_gap = gap,
  placard_title = title,
  placard_title_typeface = title_typeface,
  placard_title_size = title_size,
  placard_title_block_height_factor = title_block_height_factor,
  placard_title_alignment = title_alignment,
  placard_description = description,
  placard_description_typeface = description_typeface,
  placard_description_size = description_size,
  placard_description_alignment = description_alignment,
  placard_description_lines = description_lines,
  placard_description_line_spacing = description_line_spacing,
  placard_text_color = text_color,
  placard_substrate_color = substrate_color
) {
  color(placard_text_color) {
    placard_title_description_body(
      placard_width = placard_width,
      placard_aspect_ratio = placard_aspect_ratio,
      placard_thickness = placard_thickness,
      placard_backing_thickness = placard_backing_thickness,
      placard_border_thickness = placard_border_thickness,
      placard_border_radius = placard_border_radius,
      placard_orientation = placard_orientation,
      placard_padding = placard_padding,
      placard_gap = placard_gap,
      placard_title = placard_title,
      placard_title_typeface = placard_title_typeface,
      placard_title_size = placard_title_size,
      placard_title_block_height_factor = placard_title_block_height_factor,
      placard_title_alignment = placard_title_alignment,
      placard_description = placard_description,
      placard_description_typeface = placard_description_typeface,
      placard_description_size = placard_description_size,
      placard_description_alignment = placard_description_alignment,
      placard_description_lines = placard_description_lines,
      placard_description_line_spacing = placard_description_line_spacing
    );
  }
}

placard_title_description();
