import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, LineString
from dhydro2isg.config import CRS_28992

def _coordinate_offset(offset, xy1, xy2, xy0=None):
    """
    Calculates coordinates perpendicular to axis for a specified offset. The direction of the axis is based on the next
    and optional previous coordinate.
    """
    if xy0 is None:
        phi = np.arctan2(xy1[1] - xy2[1], xy1[0] - xy2[0])
    else:
        phi1 = np.arctan2(xy1[1] - xy2[1], xy1[0] - xy2[0])
        phi2 = np.arctan2(xy0[1] - xy1[1], xy0[0] - xy1[0])
        phi = (phi1 + phi2) / 2

    dy = np.sin(phi - 0.5 * np.pi) * offset
    dx = np.cos(phi - 0.5 * np.pi) * offset

    return [(xy1[0] + dx, xy1[1] + dy), (xy1[0] - dx, xy1[1] - dy)]


def is_left(line , point: Point):
    """
    Checks if a point is left or right from a line using crossproduct
    input shapely Line/MultiLine and point
    """
    line_start_end = line.boundary
    a, b = line_start_end.geoms[0], line_start_end.geoms[1]
    c = point
    return ((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)) > 0

def isc_preprocess(raw_df, mrc):
    """
    preprocess
    """
    two_points = raw_df.groupby(level=[0, 1]).count().iloc[:, 0] == 2
    raw_df = raw_df[raw_df.index.isin(two_points.index)]

    raw_df.loc[(raw_df["position"] == "left"), 'stretch'] *= -1

    middle_point_rows = raw_df.iloc[0::2, 1:].copy()
    middle_point_rows = middle_point_rows.assign(stretch=0, position="middel", height=middle_point_rows["btml"])

    middle_point_rows.set_index('position', append=True, inplace=True)
    raw_df.set_index('position', append=True, inplace=True)

    isc_clean = pd.concat([raw_df, middle_point_rows], axis=0).sort_index()
    isc_clean.loc[isc_clean.index.get_level_values(2) == "middel", "geometrybound"] = isc_clean.xs("middel", level=2)["geometrymid"].values

    isc_clean.reset_index(inplace=True)
    isc_clean.set_index(isc_clean["segment"].astype(str) + "-" + isc_clean["subsegment"].astype(str) + "cross", inplace=True, drop=True)
    isc_clean.index.name = "cname"
    isc_clean = isc_clean[isc_clean.groupby(level = 0).count().iloc[:, 0] == 3]

    isc_clean = isc_clean.apply(lambda x: [Point(x["geometrybound"].x, x["geometrybound"].y, x["height"]), x["segment"]], axis=1, result_type="expand")
    isc_clean.columns = ["geometry", "segment"]

    isc_clean_2 = gpd.GeoDataFrame(isc_clean[~isc_clean.index.duplicated(keep='first')]["segment"], geometry=isc_clean.groupby(level=0).apply(lambda x: LineString(x["geometry"].tolist())))

    isc_clean_2["empty"] = isc_clean_2["geometry"].apply(lambda x: len(x.boundary))
    isc_clean_2 = isc_clean_2[isc_clean_2["empty"] != 0]
    isc_clean_2["mrc"] = mrc

    isc_clean_2 = isc_clean_2[["mrc", "segment", "geometry"]]

    CROSS_SECTIONS_COLS = {"mrc": np.single,
                           "segment": str}

    isc_clean_2 = isc_clean_2.astype(CROSS_SECTIONS_COLS)
    return isc_clean_2





