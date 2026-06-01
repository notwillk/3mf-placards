$fn = 64;

// Customizable parameters
width = 75;                 // [25:200] Overall landscape width or portrait height in mm
aspect_ratio = 2;           // [1:0.1:5] Width-to-height ratio
thickness = 2;              // [0.5:0.5:10] Substrate thickness in mm
border_radius = 5;          // [0:0.5:25] Corner radius in mm
orientation = "landscape";  // [landscape, portrait]

function substrate_plate_width(substrate_width, substrate_aspect_ratio, substrate_orientation) =
  substrate_orientation == "portrait"
    ? substrate_width / substrate_aspect_ratio
    : substrate_width;

function substrate_plate_height(substrate_width, substrate_aspect_ratio, substrate_orientation) =
  substrate_orientation == "portrait"
    ? substrate_width
    : substrate_width / substrate_aspect_ratio;

module rounded_rectangle_2d(rect_width, rect_height, radius) {
  bounded_radius = min(radius, min(rect_width, rect_height) / 2);

  if (bounded_radius <= 0) {
    square([rect_width, rect_height], center = true);
  } else {
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
}

module substrate(
  substrate_width = width,
  substrate_aspect_ratio = aspect_ratio,
  substrate_thickness = thickness,
  substrate_border_radius = border_radius,
  substrate_orientation = orientation
) {
  linear_extrude(height = substrate_thickness) {
    rounded_rectangle_2d(
      substrate_plate_width(
        substrate_width,
        substrate_aspect_ratio,
        substrate_orientation
      ),
      substrate_plate_height(
        substrate_width,
        substrate_aspect_ratio,
        substrate_orientation
      ),
      substrate_border_radius
    );
  }
}

substrate();
