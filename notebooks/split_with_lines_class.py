"""Split lines at intersections using a class-based approach."""

import geopandas as gpd
from shapely import STRtree, snap
from shapely.geometry import GeometryCollection, LineString, MultiPoint, Point

EPSILON = 1e-5

class LineSplitter:
    """Split lines at intersections."""

    def __init__(self, input_gpkg, layer_name):
        """
        Initialize the LineSplitter with the input GeoPackage and layer name.

        Args:
        input_gpkg (str): Path to the input GeoPackage file.
        layer_name (str): Name of the layer to read from the GeoPackage.

        """
        self.input_gpkg = input_gpkg
        self.layer_name = layer_name
        self.gdf = gpd.read_file(self.input_gpkg, layer=self.layer_name)
        self.gdf = self.gdf.explode()  # Explode if needed for multi-part geometries
        self.sindex = self.gdf.sindex  # Spatial index for faster operations

        self.intersection_gdf = []
        self.split_lines_gdf = None
    
    def cut_line_by_points(self, line, points):
        """
        Cuts a LineString into segments based on the given points.

        Args:
        line: A shapely LineString to be cut.
        points: A list of Point objects where the LineString needs to be cut.

        Return:
        A list of LineString segments after the cuts.

        """
        # Create a spatial index for the coordinates of the LineString
        line_coords = [Point(x, y) for x, y in line.coords]
        sindex = STRtree(line_coords)

        # Sort points based on their projected position along the line
        sorted_points = sorted(points, key=lambda p: line.project(p))
        segments = []

        # Process each point, inserting it into the correct location
        start_idx = 0
        start_pt = None
        end_pt = None

        for point in sorted_points:
            # Find the closest segment on the line using the spatial index
            nearest_pt_idx = sindex.nearest(point)
            end_idx = nearest_pt_idx
            end_pt = point

            dist1 = line.project(point)
            dist2 = line.project(line_coords[nearest_pt_idx])

            if dist1 > dist2:
                end_idx = nearest_pt_idx + 1

            # Create a new segment
            new_coords = line_coords[start_idx:end_idx]
            if start_pt:  # Append start point
                new_coords = [start_pt] + new_coords
            
            if end_pt:  # Append end point
                new_coords = new_coords + [end_pt]
            
            nearest_segment = LineString(new_coords)
            start_idx = end_idx
            start_pt = end_pt

            segments.append(nearest_segment)

        # Add remaining part of the line after the last point
        if start_idx < len(line_coords):
            # If last point is not close to end point of line
            if start_pt.distance(line_coords[-1]) > EPSILON:
                remaining_part = LineString([start_pt] + line_coords[end_idx:])
                segments.append(remaining_part)

        return segments

    def find_intersections(self):
        """
        Find intersections between lines in the GeoDataFrame.

        Return:
        List of Point geometries where the lines intersect.

        """
        visited_pairs = set()
        intersection_points = []

        # Iterate through each line geometry to find intersections
        for idx, line1 in enumerate(self.gdf.geometry):
            # Use spatial index to find candidates for intersection
            indices = list(self.sindex.intersection(line1.bounds))
            indices.remove(idx)  # Remove the current index from the list
            
            for match_idx in indices:
                line2 = self.gdf.iloc[match_idx].geometry

                # Create an index pair where the smaller index comes first
                pair = tuple(sorted([idx, match_idx]))

                # Skip if this pair has already been visited
                if pair in visited_pairs:
                    continue

                # Mark the pair as visited
                visited_pairs.add(pair)

                # Only check lines that are different and intersect
                line1 = snap(line1, line2, tolerance=EPSILON)
                if line1.intersects(line2):
                    # Find intersection points (can be multiple)
                    intersections = line1.intersection(line2)

                    if intersections.is_empty:
                        continue

                    # Intersection can be Point, MultiPoint, or GeometryCollection
                    if isinstance(intersections, Point):
                        intersection_points.append(intersections)
                    elif isinstance(intersections, MultiPoint):
                        intersection_points.extend(intersections.geoms)
                    elif isinstance(intersections, GeometryCollection):
                        for item in intersections.geoms:
                            if isinstance(item, Point):
                                intersection_points.append(item)

        if intersection_points:
            self.intersection_gdf = gpd.GeoDataFrame(
                geometry=intersection_points, crs=self.gdf.crs
            )

    def split_lines_at_intersections(self):
        """
        Split lines at the given intersection points.

        Args:
        intersection_points: List of Point geometries where the lines should be split.

        Returns:
        A GeoDataFrame with the split lines.

        """
        # Create a spatial index for faster point-line intersection checks
        sindex = self.intersection_gdf.sindex
        
        # List to hold the new split line segments
        new_rows = []

        # Iterate through each intersection point to split lines at that point
        for row in self.gdf.itertuples():
            if not isinstance(row.geometry, LineString):
                continue

            # Use spatial index to find possible line candidates for intersection
            possible_matches = sindex.query(row.geometry.buffer(EPSILON))
            end_pts = MultiPoint([row.geometry.coords[0], row.geometry.coords[-1]])

            pt_list = []
            new_segments = [row.geometry]

            for idx in possible_matches:
                point = self.intersection_gdf.loc[idx].geometry
                # Check if the point is on the line
                if row.geometry.distance(point) < EPSILON:
                    if end_pts.distance(point) < EPSILON:
                        continue
                    else:
                        pt_list.append(point)

            if len(pt_list) > 0:
                # Split the line at the intersection
                new_segments = self.cut_line_by_points(row.geometry, pt_list)

            # If the line was split into multiple segments, create new rows
            for segment in new_segments:
                new_row = row._asdict()  # Convert the original row into a dictionary
                new_row['geometry'] = segment  # Update the geometry with the split one
                new_rows.append(new_row)

        self.split_lines_gdf = gpd.GeoDataFrame(
            new_rows, columns=self.gdf.columns, crs=self.gdf.crs
        )
        
        # Debugging: print how many segments were created
        print(f"Total new line segments created: {len(new_rows)}")

    def save_to_geopackage(
        self, line_layer="split_lines", intersection_layer="intersection_points"
    ):
        """
        Save the split lines and intersection points to the GeoPackage.

        Args:
        line_layer: split lines layer name in the GeoPackage.
        intersection_layer: layer name for intersection points in the GeoPackage.

        """
        # Save intersection points and split lines to the GeoPackage
        if len(self.intersection_gdf) > 0:
            self.intersection_gdf.to_file(
                self.input_gpkg, layer="intersection_points", driver="GPKG"
            )

        if len(self.split_lines_gdf) > 0:
            self.split_lines_gdf.to_file(
                self.input_gpkg, layer="split_lines", driver="GPKG"
            )
    
    def process(self):
        """Find intersection points, split lines at intersections."""
        self.find_intersections()

        if not self.intersection_gdf.empty:
            # Split the lines at intersection points
            self.split_lines_at_intersections()
        else:
            print("No intersection points found, no lines to split.")
            
def split_with_lines(input_gpkg, layer_name):
    splitter = LineSplitter(input_gpkg, layer_name)
    splitter.process()
    splitter.save_to_geopackage()

if __name__ == "__main__":
    input_gpkg = r"I:\Temp\footprint_final.gpkg"
    layer_name = "merged_lines_original"

    splitter = LineSplitter(input_gpkg, layer_name)
    splitter.process()
    splitter.save_to_geopackage()