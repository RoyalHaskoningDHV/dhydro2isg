from shapely.ops import  LineString, Point
import numpy as np
import geopandas as gpd
from dhydro2isg.config import INTERSECTION_BUFFER
from typing import Optional
from shapely.ops import nearest_points


def get_chainage(point: Point, line: LineString, buffer=INTERSECTION_BUFFER):
    """
    Get chainage of point along a line
    Args:
        point: Shapely point object
        line: Shapely Linestring
        buffer: intersection buffer (float)

    Returns: distance of point along the line (chainage)

    """
    if line.intersects(point.buffer(buffer)):
        return line.project(point)
    else:
        return None

# def _get_nearest_zvalue(gdf1, gdf2) -> np.single:
#     """
#     for a point: Get the nearest minimum z-value (ahn) from cross section boundary points . (same segment)
#     """
#     gdf2_segment_filter = gdf2[gdf2["segment"] == gdf1["segment"]]
#     gdf2_segment_filter["centroid"] = gdf2_segment_filter["geometry"].centroid
#     gdf2_centroid_union= gdf2_segment_filter["centroid"].unary_union

#     if gdf1["geometry"] is not None and gdf2_centroid_union is not None:
#         nearest_point = nearest_points(gdf1["geometry"], gdf2_centroid_union)
#         loc = gdf2_segment_filter[gdf2_segment_filter["centroid"].values == nearest_point[1]]
#         res = loc['geometry'].apply(lambda geom: np.min([coord[2] for coord in [geom.coords[0], geom.coords[-1]]])).values[0]
#         return res


def seg_overlay(gdf1: gpd.GeoDataFrame, gdf2: gpd.GeoDataFrame, bufferdist: int, minlength: Optional[int],
                save_deleted: bool, save_deleted_folder: Optional[str])\
        -> gpd.GeoDataFrame:
    """
    Overlays two geometries and deletes part of geodataframe that overlaps
    Args:
        gdf1: Geodataframe that has to be deleted from gdf2
        gdf2: Geodataframe used to check overlap with
        bufferdist: bufferdistance of gdf2
        minlength: delete lines from gdf1 smaller that minlength

    Returns:
        A geodataframe from which a part of the geometries is deleted based on overlay with the second geodataframe

    """
    if gdf1.crs is not gdf2.crs:
        raise Exception(f'crs systems of input files are not equal. gdf1:{gdf1.crs} gdf2:{gdf2.crs}')

    buffer_seg = gpd.GeoDataFrame(geometry=gdf2.buffer(bufferdist))

    gdf1.reset_index(inplace=True)
    second_seg_new = gpd.overlay(gdf1, buffer_seg, how="difference", keep_geom_type=False)
    second_seg_new.set_index("label", inplace=True)
    gdf1.set_index("label", inplace=True)

    if minlength:
        second_seg_new = second_seg_new[second_seg_new.length >= minlength]

    if save_deleted:
        index_in_new = gdf1.index.isin(second_seg_new.index)
        gdf_deleted = gdf1.loc[~index_in_new]
        gdf_deleted.to_file(f'{save_deleted_folder}/deleted_lines.shp')
        print(f'Deleted lines saved to: {save_deleted_folder}/deleted_lines.shp')

    return second_seg_new
