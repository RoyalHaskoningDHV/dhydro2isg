import os
import itertools
import warnings
from datetime import datetime, timedelta
from operator import itemgetter
from tqdm import tqdm
import geopandas as gpd
import netCDF4 as nc
import numpy as np
import pandas as pd
import xarray as xr

from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point
from pathlib import Path

from dhydro2isg.stf import STF
from dhydro2isg.config import STRUCTURES_COLS, DISCHARGE_RELATIONS_COLS
from dhydro2isg.dhydro_geometry import create_branches, create_crosssections, yz_to_xyz, crsloc_ini_to_dataframe, crsdef_ini_to_dataframe

def sjoin_map_with_net(map_gdf, net_gdf):
    """Alternative to ckdnearest: 
    Find on which segment a point is located, by buffering the point and intersecting"""
    buffered_points = map_gdf.copy()
    buffered_points["geometry"] = buffered_points['geometry'].buffer(0.01)
    sjoined = gpd.sjoin(buffered_points, net_gdf)
    sjoined_map = map_gdf.merge(sjoined[["node_name", "segment"]], on="node_name")
    return sjoined_map


def ckdnearest(gdfA, gdfB, gdfB_cols=["segment"]):
    A = np.concatenate([np.array(geom.coords) for geom in gdfA.geometry.to_list()])
    B = [np.array(geom.coords) for geom in gdfB.geometry.to_list()]
    B_ix = tuple(
        itertools.chain.from_iterable(
            [itertools.repeat(i, x) for i, x in enumerate(list(map(len, B)))]
        )
    )
    B = np.concatenate(B)
    ckd_tree = cKDTree(B)
    dist, idx = ckd_tree.query(A, k=1)
    idx = itemgetter(*idx)(B_ix)
    gdf = pd.concat(
        [
            gdfA,
            gdfB.loc[idx, gdfB_cols].reset_index(drop=True),
            pd.Series(dist, name="dist"),
        ],
        axis=1,
    )
    return gdf

def parse_nc_resolution(s: str):
    from datetime import timedelta
    date_part, time_part = s[1:].split('T')   # remove leading 'P'
    _, _, days = map(int, date_part.split('-'))
    h, m, sec = map(int, time_part.split(':'))
    td = timedelta(days=days, hours=h, minutes=m, seconds=sec)
    return td


def create_topflow_map_gdf(dhydro_map_nc, epsg, resistance, infiltration, start_time, end_time, aggregation_method="mean"):
    """
    This step will collect calculated values from DHydro from the map.nc file 
    This includes information like x, y coordinates, water level, water depth and node names
    Since the water depth can vary through the calculation, a time window at the end
    of the timeseries is used, and aggregated using the aggregation method specified. 

    Parameters
    ----------
    dhydro_map_nc : str
        Path to the DHydro map.nc file
    epsg : int
        EPSG code of the coordinate reference system
    resistance : float
        Resistance value, only used to fill ISG file later on
    infiltration : float
        Infiltration value, only used to fill ISG file later on
    window : str
        Time window to use for the aggregation (default: "1D")
    aggregation_method : str
        Aggregation method to use for the aggregation (default: "mean")

    Returns
    -------
    gdf : geopandas.GeoDataFrame
        GeoDataFrame with the calculated values
    """
    # parse start/end as pandas Timestamps (will be localized to map tz if needed)
    start_time_dt = pd.to_datetime(start_time)
    end_time_dt = pd.to_datetime(end_time)
    # window = end_time_dt - start_time_dt
    
    source = nc.Dataset(dhydro_map_nc)
    td = parse_nc_resolution(source.time_coverage_resolution)
    map_start = pd.to_datetime(source.time_coverage_start)
    map_end = pd.to_datetime(source.time_coverage_end)
    timesteps = pd.date_range(start=map_start, end=map_end, freq=td)
    print(f"Map data time range: {map_start} to {map_end}, resolution: {td}")
    # Ensure comparisons use the same timezone-awareness
    map_tz = getattr(timesteps, 'tz', None)
    if map_tz is not None:
        start_ts = start_time_dt.tz_localize(map_tz) if start_time_dt.tzinfo is None else start_time_dt.tz_convert(map_tz)
        end_ts = end_time_dt.tz_localize(map_tz) if end_time_dt.tzinfo is None else end_time_dt.tz_convert(map_tz)
    else:
        start_ts = start_time_dt
        end_ts = end_time_dt

    if start_ts < map_start or end_ts > map_end:
        raise ValueError(f"start_time and end_time must be within the map data range: {map_start} to {map_end}")
    
    window_index = (timesteps >= start_ts) & (timesteps <= end_ts)
    # timesteps_seconds = ((timesteps[-1] - timesteps[timesteps_mask]) / pd.Timedelta(seconds=1)).values.astype(int)
    if not window_index.any():
        raise ValueError(f"No timesteps found within the specified time range: {start_ts} to {end_ts}")
    
    nodes_list = []
    for i in tqdm(range(len(source.variables["mesh1d_node_x"]))):
        node_str = listToString(source["mesh1d_node_id"][i])

        # calculate the aggregated waterdepth within the specified window
        aggregated_waterlevel = getattr(source.variables["mesh1d_s1"][window_index, i], aggregation_method)()
        aggregated_waterdepth = getattr(source.variables["mesh1d_waterdepth"][window_index, i], aggregation_method)()

        # handle missing values for aggregated waterlevels
        if isinstance(aggregated_waterlevel, np.ma.core.MaskedConstant):

            # create temporary place to store the netCDF data
            temp_waterlevel = []
            temp_waterdepth = []

            for step in window_index:
                temp_waterlevel.append(source["mesh1d_s1"][step, i])
                temp_waterdepth.append(source["mesh1d_waterdepth"][step, i].data)

            temp_waterlevel_missing = source.variables['mesh1d_flowelem_bl'][:].data[i]
            temp_waterdepth_missing = 0

            # adapt content of the tem variables if waterlevel contains a missing variable
            for step in range(len(temp_waterlevel)):
                if isinstance(temp_waterlevel[step], np.ma.core.MaskedConstant):
                    temp_waterlevel[step] = temp_waterlevel_missing
                    temp_waterdepth[step] = temp_waterdepth_missing
                    
            # redo aggregation
            aggregated_waterlevel = getattr(np, aggregation_method)(temp_waterlevel)
            aggregated_waterdepth = getattr(np, aggregation_method)(temp_waterdepth)

        nodes_list.append(
            [
                Point(
                    source.variables["mesh1d_node_x"][i],
                    source.variables["mesh1d_node_y"][i],
                ),
                float(aggregated_waterlevel),
                float(aggregated_waterdepth),
                node_str,
            ]
        )
    df = pd.DataFrame(nodes_list, columns=["geometry", "wlvl", "wdepth", "node_name"])
    gdf = gpd.GeoDataFrame(df, geometry="geometry")
    gdf.set_crs(epsg, inplace=True)
    gdf["btml"] = gdf["wlvl"] - gdf["wdepth"]
    gdf["resis"] = resistance
    gdf["inff"] = infiltration
    gdf["type"] = "calc"
    gdf["id"] = gdf.index
    return gdf

def listToString(s):
    # initialize an empty string
    str1 = ""

    # traverse in the string
    for ele in s:
        # Check if ele is a byte-like object and decode if necessary
        if isinstance(ele, bytes):
            str1 += ele.decode("utf-8")
        else:
            str1 += str(ele)
    
    str1 = str1.strip()
    # return string
    return str1

def create_topflow_net_gdf(dhydro_net_nc, epsg):
    # ds = nc.Dataset(dhydro_net_nc)
    ds = xr.open_dataset(dhydro_net_nc)

    # dynamisch gebruik variabelen voorbereiden
    if 'network1d_geom_x' in ds:
        network_key = 'network1d'
    elif 'network_geom_x' in ds:
        network_key = 'network'
    else:
        network_key = 'network'

    # maak een geodataframe van alle nodes
    geom_x = f'{network_key}_geom_x'
    geom_y = f'{network_key}_geom_y'

    df = pd.concat([pd.Series(ds[geom_x].values), pd.Series(ds[geom_y].values)], axis=1)
    df.columns = [geom_x, geom_y]
    gdf = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df[geom_x], df[geom_y])
    )

    # aantal nodes per branch id
    node_count = ds[f'{network_key}_geom_node_count'].values
    branch_id_list = []
    for i in range(len(ds[f'{network_key}_branch_id'].values.astype(str))):
        branch_str = listToString(ds[f'{network_key}_branch_id'].values.astype(str)[i])
        branch_id_list.append(branch_str)
    df_branches = pd.concat([pd.Series(node_count), pd.Series(branch_id_list)], axis=1)
    df_branches.columns = ["network_geom_node_count", "segment"]

    # maak aparte linestring aan voor elke branch id met alle nodes die erbij horen
    df_branches["line_geometry"] = ""
    df_branches["start_node"] = ""
    df_branches["end_node"] = ""

    for j in tqdm(range(len(df_branches))):
        if j == 0:
            start_node = 0
            end_node = 0 + df_branches["network_geom_node_count"][j]
            df_branches.loc[j, "start_node"] = start_node
            df_branches.loc[j, "end_node"] = end_node
            linestring = LineString(
                gdf.iloc[df_branches["start_node"][j] : df_branches["end_node"][j]][
                    "geometry"
                ].values
            )
            with warnings.catch_warnings():  # This deprication warning is not relevant to this situation
                df_branches.loc[j, "line_geometry"] = linestring
        else:
            start_node = df_branches["network_geom_node_count"][:j].sum()
            end_node = start_node + df_branches["network_geom_node_count"].iloc[j]
            df_branches.loc[j, "start_node"] = start_node
            df_branches.loc[j, "end_node"] = end_node
            linestring = LineString(
                gdf.iloc[df_branches["start_node"][j] : df_branches["end_node"][j]][
                    "geometry"
                ].values
            )
            with warnings.catch_warnings():  # This deprication warning is not relevant to this situation
                df_branches.loc[j, "line_geometry"] = linestring

    gdf_branches = gpd.GeoDataFrame(df_branches, geometry=df_branches.line_geometry)
    del gdf_branches["line_geometry"]
    gdf_branches["label"] = gdf_branches["segment"].str.strip()
    gdf_branches.set_crs(epsg, inplace=True)
    return gdf_branches


def make_calculation_points_temporal(x_calculation_points, start_time, end_time):
    start_time_dt = datetime.strptime(start_time, "%Y-%m-%d")
    end_time_dt = datetime.strptime(end_time, "%Y-%m-%d")
    df_length = len(x_calculation_points)
    simulation_duration = end_time_dt - start_time_dt
    # date_list = [
    #     start_time_dt + timedelta(days=x) for x in range(simulation_duration.days + 1)
    # ]
    date_list = [start_time_dt, end_time_dt]
    rdf = pd.DataFrame(
        np.repeat(x_calculation_points.values, len(date_list), axis=0),
        columns=x_calculation_points.columns,
    )
    rdf["datetime"] = date_list * df_length
    return rdf

def hydamo_to_xyz_lines(hydamo_gdf, epsg, x_segments, mrc):
    geo_df2 = hydamo_gdf.groupby(["profielcode", "ruwheidswaardehoog"])[
        "geometry"
    ].apply(lambda x: LineString(x.tolist()))
    geo_df2 = gpd.GeoDataFrame(geo_df2, geometry="geometry")
    geo_df2.index.rename(
        {"profielcode": "cname", "ruwheidswaardehoog": "mrc"}, inplace=True
    )
    geo_df2['mrc'] = [mrc]*len(geo_df2)
    geo_df2.set_crs(epsg, inplace=True)
    geo_df2_with_seg_name = gpd.sjoin(geo_df2, x_segments, how='left')
#     geo_df2_with_seg_name = geo_df2.sjoin(x_segments, how="left")
    return geo_df2_with_seg_name[["geometry", "segment"]]

def dhydro_to_crosssection(dhydro_network_nc, crossloc_ini, crossdef_ini, epsg=None):
    branches = create_branches(dhydro_network_nc, output_folder=False, epsg=epsg)
    # crs_loc_df = pd.DataFrame([cs.__dict__ for cs in CrossLocModel(crossloc_ini).crosssection])
    crs_loc_df = crsloc_ini_to_dataframe(crossloc_ini)
    
    crs_def_df = crsdef_ini_to_dataframe(crossdef_ini)
    crs_loc_df['profile'] = crs_loc_df.apply(lambda x: yz_to_xyz(branches=branches,
                                                                 branch_id=x['branchid'],
                                                                 chainage=float(x['chainage']),
                                                                 crs_def_id=x['definitionid'],
                                                                 crs_def_df=crs_def_df), axis=1)
    return crs_loc_df

def dhydro_to_stf(dhydro_folder: str, start_time: str, end_time: str,resistance: float=1, infiltration: float=0.3, mrc: float=25,output_name: str="output",
                    stf_output_folder=None, relpath_network_nc: str="fm/network.nc", relpath_map_nc: str="fm/output/DFM_map.nc", relpath_crossloc_ini: str="fm/crsloc.ini", relpath_crossdef_ini: str="fm/crsdef.ini", 
                  epsg=28992, aggregation_method="mean"):
    
    """
    Convert D-HYDRO network and map data to STF (Sobek TopoFlow) format.
    This function processes D-HYDRO NetCDF files and configuration files to create
    a complete STF object with network topology, locations, calculation points,
    cross-sections, and structures.
    Parameters
    ----------
    dhydro_network_nc : str
        Path to the D-HYDRO network NetCDF file containing network topology data.
    dhydro_map_nc : str
        Path to the D-HYDRO map NetCDF file containing map layer data.
    crossloc_ini : str
        Path to the D-HYDRO cross-section locations INI configuration file.
    crossdef_ini : str
        Path to the D-HYDRO cross-section definitions INI configuration file.
    output_name : str
        Base name for output files (used as prefix for shapefile and CSV exports).
    start_time : str
        Start time for the temporal calculation points (format: yyyy-mm-dd).
    end_time : str
        End time for the temporal calculation points (format: yyyy-mm-dd).
    resistance : float, optional
        Resistance coefficient for map layers (default: 1).
    infiltration : float, optional
        Infiltration rate for map layers (default: 0.3).
    mrc : float, optional
        Main river channel value for cross-sections (default: 25).
    epsg : int, optional
        EPSG code for the coordinate reference system (default: 28992, RD New).
    output_folder : str, optional
        Path to output folder for exporting shapefiles and CSV files.
        If None, files are not exported (default: None).
    aggregation_window : str, optional
        Time window duration (default: "1D") specified as a pandas Timedelta-compatible 
        string (e.g., "1D", "12H", "3600S"). Aggregation is performed on all timesteps 
        within this window from the end of the simulation.
    aggregation_method : str, optional
        aggregation_method for missing water levels and water depths. NumPy aggregation function name (default: "mean"). Applied to water level and 
        depth arrays (e.g., "mean", "max", "min"). Used via getattr(np, aggregation_method).
    Returns
    -------
    STF
        A STF object populated with segments, locations, calculation points,
        cross-sections, and structures data ready for use in Sobek TopoFlow.
    """
    
    # Define full paths to input files
    dh_network_nc = os.path.join(dhydro_folder, relpath_network_nc)
    dh_map_nc = os.path.join(dhydro_folder, relpath_map_nc)
    dh_crossloc_ini = os.path.join(dhydro_folder, relpath_crossloc_ini)
    dh_crossdef_ini = os.path.join(dhydro_folder, relpath_crossdef_ini)
    
    # Validate input parameters
    required_files = {
        'dhydro_network_nc': dh_network_nc,
        'dhydro_map_nc': dh_map_nc,
        'crossloc_ini': dh_crossloc_ini,
        'crossdef_ini': dh_crossdef_ini
    }
    
    for file_name, file_path in required_files.items():
        if not Path(file_path).exists():
            raise FileNotFoundError(f"{file_name} not found: {file_path}")
    
    os.mkdir(stf_output_folder, exist_ok=True) if stf_output_folder else None
    
    try:
        datetime.strptime(start_time, "%Y-%m-%d")
        datetime.strptime(end_time, "%Y-%m-%d")
    except ValueError:
        raise ValueError("start_time and end_time must be in format '%Y-%m-%d' (e.g., '2018-01-01')")
    
    
    net_gdf = create_topflow_net_gdf(dh_network_nc, epsg)
    map_gdf = create_topflow_map_gdf(dh_map_nc, epsg, resistance, infiltration, start_time=start_time, end_time=end_time, aggregation_method=aggregation_method)
    # map_with_network = ckdnearest(map_gdf, net_gdf)
    map_with_network = sjoin_map_with_net(map_gdf, net_gdf)
    map_with_network["cname"] = map_with_network.apply(lambda row: str(row["node_name"]) + str(row["segment"]), 1)

    segments = net_gdf[["label", "geometry"]]

    if stf_output_folder:
        segments.to_file(f"{stf_output_folder}/{output_name}_segments.shp")

    locations = map_with_network[["cname", "type", "segment", "geometry"]]
    if stf_output_folder:
        locations.to_file(f"{stf_output_folder}/{output_name}_locations.shp")

    calculation_points = map_with_network[["cname", "wlvl", "btml", "resis", "inff"]]
    calculation_points = make_calculation_points_temporal(calculation_points, start_time, end_time)
    if stf_output_folder:
        calculation_points.to_csv(f"{stf_output_folder}/{output_name}_calculation_points.csv")

    cross_sections = dhydro_to_crosssection(dh_network_nc, dh_crossloc_ini, dh_crossdef_ini, epsg=epsg)
    cross_sections.rename(columns={'profile': 'geometry',
                                   'id': 'cname',
                                   'branchid': 'segment'},
                          inplace=True)
    cross_sections['mrc'] = mrc
    cross_sections = cross_sections.dropna(subset=["geometry"])
    cross_sections = gpd.GeoDataFrame(geometry=cross_sections['geometry'],
                                      data=cross_sections[['cname', 'segment', 'mrc']],
                                      crs=f'EPSG:{epsg}')
    if stf_output_folder:
        cross_sections.to_file(f"{stf_output_folder}/{output_name}_cross_sections.shp")

    structures = pd.DataFrame(columns=STRUCTURES_COLS)
    qh = pd.DataFrame(columns=DISCHARGE_RELATIONS_COLS)

    stf = STF()
    stf.import_from_gdf(segments=segments, locations=locations, calculation_points=calculation_points,
                        structures=structures, qh=qh, cross_sections=cross_sections.reset_index())
    return stf

    
if __name__ == '__main__':
    import sys
    sys.path.insert(0, r'c:\Git\D-HYDRO2iMOD\dhydro2isg')
    df = create_topflow_map_gdf(dhydro_map_nc=r"c:\Users\905872\Haskoning\P-BK8839-WSVV-detachering-hydroloog - Team\WIP\01_modelbouw\Modellen\C Boven-heigraaf\Oud\T10_1D_1912_v0.18_basis\T10_1D_1912_v0.18_basis.dsproj_data\DFM\output\DFM_map.nc", epsg=28992, resistance=1, infiltration=0.3, window="1D", aggregation_method="mean", start_time="2000-01-01", end_time="2000-01-10")
    df