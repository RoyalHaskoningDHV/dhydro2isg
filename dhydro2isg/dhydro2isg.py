import itertools
import warnings
from datetime import datetime, timedelta
from operator import itemgetter
from hydrolib.core.dflowfm.crosssection.models import CrossDefModel, CrossLocModel
from pydantic import ValidationError
import collections

import geopandas as gpd
import netCDF4 as nc
import numpy as np
import pandas as pd
import xarray as xr

from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point
from pathlib import Path

from top_flow.stf import STF
from top_flow.config import STRUCTURES_COLS, DISCHARGE_RELATIONS_COLS
from top_flow.dhydro_geometry import create_branches, create_crosssections, yz_to_xyz

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

def create_topflow_map_gdf(dhydro_map_nc, epsg, resistance, infiltration, window = "1D", aggregation_method="mean"):
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
    source = nc.Dataset(dhydro_map_nc)
    nodes_list = []
    for i in range(len(source.variables["mesh1d_node_x"])):
        node_str = listToString(source["mesh1d_node_id"][i])

        # convert time axis to seconds (if needed), then to seconds before end
        unit = source.variables["time"].units.split(" ")[0]
        multiply_to_seconds = {"seconds": 1, "minutes": 60, "hours": 3600}
        timesteps_seconds = source.variables["time"][:].data * multiply_to_seconds[unit]
        timesteps_seconds = (timesteps_seconds - timesteps_seconds[-1]) * -1  # seconds before end 
        timesteps_seconds = timesteps_seconds.astype(int)
        
        # convert the window to seconds and find the corresponding index from timesteps_seconds
        window_seconds = pd.to_timedelta(window).total_seconds()
        window_index = np.where(timesteps_seconds <= window_seconds)[0]

        # calculate the aggregated waterdepth within the specified window
        aggregated_waterlevel = getattr(source.variables["mesh1d_s1"][window_index, i], "mean")()
        aggregated_waterdepth = getattr(source.variables["mesh1d_waterdepth"][window_index, i], "mean")()

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

    for j in range(len(df_branches)):
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
    date_list = [
        start_time_dt + timedelta(days=x) for x in range(simulation_duration.days + 1)
    ]
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
    crs_loc_df = pd.DataFrame([cs.__dict__ for cs in CrossLocModel(crossloc_ini).crosssection])
    
    try:
        crs_def_model = CrossDefModel(crossdef_ini)
    except ValidationError as e:
        # Handle duplicate friction specification error
        warnings.warn(f"Validation error in crossdef file: {e}")
        warnings.warn("Attempting to fix duplicate friction specifications by removing frictionids where both are specified.")
        
        # Read and fix the INI file manually
        from pathlib import Path
        
        # Read the file line by line and fix duplicate friction specifications
        temp_file = Path(crossdef_ini).parent / f"{Path(crossdef_ini).stem}_temp.ini"
        
        with open(crossdef_ini, 'r') as f_in, open(temp_file, 'w') as f_out:
            current_section_lines = []
            in_section = False
            has_friction_types_or_values = False
            
            for line in f_in:
                stripped = line.strip()
                
                # Check if this is a section header
                if stripped.startswith('[') and stripped.endswith(']'):
                    # Write the previous section (if any) after processing
                    if in_section and current_section_lines:
                        # Check if we need to remove frictionIds
                        if has_friction_types_or_values:
                            # Filter out frictionIds line
                            filtered_lines = [l for l in current_section_lines 
                                            if not l.strip().lower().startswith('frictionids')]
                            f_out.writelines(filtered_lines)
                        else:
                            f_out.writelines(current_section_lines)
                    
                    # Start new section
                    current_section_lines = [line]
                    in_section = True
                    has_friction_types_or_values = False
                else:
                    # Add line to current section
                    if in_section:
                        current_section_lines.append(line)
                        # Check for friction specification
                        lower_line = stripped.lower()
                        if lower_line.startswith('frictiontypes') or lower_line.startswith('frictionvalues'):
                            has_friction_types_or_values = True
            
            # Write the last section
            if in_section and current_section_lines:
                if has_friction_types_or_values:
                    filtered_lines = [l for l in current_section_lines 
                                    if not l.strip().lower().startswith('frictionids')]
                    f_out.writelines(filtered_lines)
                else:
                    f_out.writelines(current_section_lines)
        
        # Load the fixed file
        crs_def_model = CrossDefModel(temp_file)
        
        # Clean up temp file
        temp_file.unlink()
    
    crs_def_df = pd.DataFrame([cs.__dict__ for cs in crs_def_model.definition])
    crs_loc_df['profile'] = crs_loc_df.apply(lambda x: yz_to_xyz(branches=branches,
                                                                 branch_id=x['branchid'],
                                                                 chainage=x['chainage'],
                                                                 crs_def_id=x['definitionid'],
                                                                 crs_def_df=crs_def_df), axis=1)
    return crs_loc_df
    # crs_locations = create_crosssections(branches, crossloc_ini, output_folder=False)
    # crs_def = CrossDefModel(crossdef_ini)
    # crs_def_df = pd.DataFrame([cs.__dict__ for cs in crs_def.definition])





def dhydro_to_stf(dhydro_network_nc, dhydro_map_nc, crossloc_ini, crossdef_ini, output_name,
                  start_time, end_time, resistance=1, infiltration=0.3, mrc=25, epsg=28992, output_folder=None, 
                  aggregation_window="1D", aggregation_method="mean"):
    net_gdf = create_topflow_net_gdf(dhydro_network_nc, epsg)
    map_gdf = create_topflow_map_gdf(dhydro_map_nc, epsg, resistance, infiltration, window=aggregation_window, aggregation_method=aggregation_method)
    # map_with_network = ckdnearest(map_gdf, net_gdf)
    map_with_network = sjoin_map_with_net(map_gdf, net_gdf)
    map_with_network["cname"] = map_with_network.apply(lambda row: str(row["node_name"]) + str(row["segment"]), 1)

    segments = net_gdf[["label", "geometry"]]

    if output_folder:
        segments.to_file(f"{output_folder}/{output_name}_segments.shp")

    locations = map_with_network[["cname", "type", "segment", "geometry"]]
    if output_folder:
        locations.to_file(f"{output_folder}/{output_name}_locations.shp")

    calculation_points = map_with_network[["cname", "wlvl", "btml", "resis", "inff"]]
    calculation_points = make_calculation_points_temporal(calculation_points, start_time, end_time)
    if output_folder:
        calculation_points.to_csv(f"{output_folder}/{output_name}_calculation_points.csv")

    cross_sections = dhydro_to_crosssection(dhydro_network_nc, crossloc_ini, crossdef_ini, epsg=epsg)
    cross_sections.rename(columns={'profile': 'geometry',
                                   'id': 'cname',
                                   'branchid': 'segment'},
                          inplace=True)
    cross_sections['mrc'] = mrc
    cross_sections = cross_sections.dropna(subset=["geometry"])
    cross_sections = gpd.GeoDataFrame(geometry=cross_sections['geometry'],
                                      data=cross_sections[['cname', 'segment', 'mrc']],
                                      crs=f'EPSG:{epsg}')
    if output_folder:
        cross_sections.to_file(f"{output_folder}/{output_name}_cross_sections.shp")

    structures = pd.DataFrame(columns=STRUCTURES_COLS)
    qh = pd.DataFrame(columns=DISCHARGE_RELATIONS_COLS)

    stf = STF()
    stf.import_from_gdf(segments=segments, locations=locations, calculation_points=calculation_points,
                        structures=structures, qh=qh, cross_sections=cross_sections.reset_index())
    return stf


if __name__ == '__main__':
    folder = Path(r'd:\DHydro\T Merkske\Scenario_1_Referentie\Merkske_v14_Q40.dsproj_data\DFM')
    output_folder = folder.parents[2]/'STF_OUTPUT_5'
    wip_folder = output_folder/'WIP'
    wip_folder.mkdir(exist_ok=True, parents=True)

    start_time = "2018-01-01"
    end_time = "2018-01-03"

    dhydro_network_nc = folder/'input'/'Merske_Q100_net.nc'
    dhydro_map_nc = folder/'output'/'DFM_map.nc'
    crossloc_ini = folder/'input'/'crsloc.ini'
    crossdef_ini = folder/'input'/'crsdef.ini'


    stf = dhydro_to_stf(dhydro_network_nc=dhydro_network_nc,
                        dhydro_map_nc=dhydro_map_nc,
                        crossloc_ini=crossloc_ini,
                        crossdef_ini=crossdef_ini,
                        output_name="Merkske_test",
                        start_time=start_time,
                        end_time=end_time,
                        resistance=1,
                        infiltration=0.3,
                        mrc=25,
                        epsg=28992,
                        output_folder=wip_folder)

    stf.clean_stf(minlength=10)
    stf.export_to_shape(export_folder=str(output_folder), filename='Merkske_Q40_test')
    stf.export_to_isg(export_folder=str(output_folder), filename='Merkske_Q40_test')

    new = STF()
    new.import_from_shape(import_folder=output_folder, prefix_filename='Merkske_Q40_test')
    new.export_to_isg("Merkske_Q40_test_re-read", export_folder=str(output_folder))