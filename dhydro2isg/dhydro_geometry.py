import pandas as pd
import geopandas as gpd
import xarray as xr
from shapely.geometry import LineString, Point
from shapely.errors import ShapelyDeprecationWarning
from pathlib import Path
import warnings
from hydrolib.core.dflowfm.crosssection.models import CrossLocModel


#TODO: Create an MDU based class

def create_branches(network_nc, output_folder=False, epsg=None):
    """
        Create geometry dataset of the branches of the DHydro network
        # TODO: use MDU to find crossloc file

        Args:
            network_nc: path to the _net.nc file of the DHydro network
            output_folder: either False (do not export) or a path to the desired output folder
            epsg: EPSG code to use for the CRS (optional, will try to read from network file if not provided)

        Returns:
            branches: A GeoDataFrame of the branches in the DHydro Network
        """
    if output_folder:
        output_folder = Path(output_folder)

    ds = xr.open_dataset(network_nc)

    # network_key resembles the prefix of the geom_x, geom_y, etc elements in the net_nc. Logic of the exact prexif is currently unknown to script's developers.
    if 'network1d_geom_x' in ds:
        network_key = 'network1d'
    elif 'Network_geom_x' in ds:
        network_key = 'Network'
    else:
        network_key = 'network'

    if epsg is not None:
        crs = f'EPSG:{epsg}'
    elif 'projected_coordinate_system' in ds:
        epsg_code = ds.projected_coordinate_system.EPSG_code
        if epsg_code == 0 or epsg_code is None:
            warnings.warn("Caution: invalid EPSG code (0) found in network file, assuming default CRS (EPSG:28992 RD New)")
            crs = 'EPSG:28992'
        else:
            crs = f'EPSG:{epsg_code}'
    else:
        warnings.warn("Caution: no CRS found in network file, assuming default CRS (EPSG:28992 RD New)")
        crs = 'EPSG:28992'

    # common variables
    geom_x = f'{network_key}_geom_x'
    geom_y = f'{network_key}_geom_y'

    # Create points for all vertexes
    df_network = pd.concat([pd.Series(ds[geom_x].values), pd.Series(ds[geom_y].values)],
                   axis=1)
    df_network.columns = [geom_x, geom_y]
    gdf_network = gpd.GeoDataFrame(df_network, geometry=gpd.points_from_xy(df_network[geom_x], df_network[geom_y]))

    df_branches = pd.DataFrame({'node_count': ds[f'{network_key}_geom_node_count'].values,
                                'branchid': ds[f'{network_key}_branch_id'].values.astype(str),
                                'user_length': ds[f'{network_key}_edge_length'].values,
                                'line_geometry': None,
                                'start_node': None,
                                'end_node': None})

    for j in range(len(df_branches)):
        if j == 0:
            start_node = 0
            end_node = 0 + df_branches['node_count'][j]
        else:
            start_node = df_branches['node_count'][:j].sum()
            end_node = start_node + df_branches['node_count'].iloc[j]

        df_branches.loc[j, 'start_node'] = start_node
        df_branches.loc[j, 'end_node'] = end_node
        linestring = LineString \
            (gdf_network.iloc[df_branches['start_node'][j] : df_branches['end_node'][j]]['geometry'].values)
        with warnings.catch_warnings():  # This deprication warning is not relevant to this situation
            warnings.filterwarnings("ignore", category=ShapelyDeprecationWarning)
            df_branches.loc[j, 'line_geometry'] = linestring

    branches = gpd.GeoDataFrame(df_branches, geometry=df_branches.line_geometry,
                                crs = crs)

    del branches['line_geometry']
    branches['branchid'] = branches['branchid'].str.strip()
    if output_folder:
        branches.to_file(output_folder /'branches.shp')
    return branches

def create_crosssections(branches: gpd.GeoDataFrame, crossloc_ini: Path, output_folder=False):
    """
    Create geometry dataset of the crosssection locations, by projecting the points on the branch-network.

    # TODO: use MDU to find crossloc file

    Args:
        branches: geodataframe of the network's branches
        crossloc_ini: pathname to the crosssection location (ini) file
        output_folder: either False (do not export) or a path to the desired output folder

    Returns:
        gdf_cross_loc: GeoDataFrame of the crosssection locations
    """
    if output_folder:
        output_folder = Path(output_folder)

    crossloc_source = Path(crossloc_ini)
    cross_loc = pd.DataFrame([cs.__dict__ for cs in CrossLocModel(crossloc_source).crosssection])

    df_cross_loc = pd.merge(cross_loc, branches, on='branchid', how='left')
    gdf_cross_loc = gpd.GeoDataFrame(df_cross_loc, geometry='geometry', crs=branches.crs)
    gdf_cross_loc['length'] = gdf_cross_loc['geometry'].length
    gdf_cross_loc['scaled_offset'] = gdf_cross_loc['chainage'].astype(float) / gdf_cross_loc['user_length'] * gdf_cross_loc['length']

    # Use chainage to find location of crosssections
    gdf_cross_loc['cross_loc_geom'] = gdf_cross_loc['geometry'].interpolate \
        (gdf_cross_loc['scaled_offset'].astype(float))
    gdf_cross_loc.rename(columns={'geometry': 'branch_geometry'}, inplace=True)
    gdf_cross_loc = gdf_cross_loc[['id', 'branchid', 'chainage', 'scaled_offset', 'definitionid', 'cross_loc_geom', 'user_length', 'length']]
    gdf_cross_loc = gpd.GeoDataFrame(gdf_cross_loc, geometry='cross_loc_geom', crs=branches.crs)
    if output_folder:
        gdf_cross_loc.to_file(output_folder /'crosssection_locations.shp')
    return gdf_cross_loc


def select_crosssection_locations(crosssection_locations, shapefile_path):
    """
    Make a selection of the crosssection locations based on a polygon (from shapefile)
    Assumes both crosssection_locations and the shapefile are in the same coordinate system.
    TODO: Test if selection works with multi-polygons or multiple features
    Args:
        crosssection_locations: GeoDataFrame of all crosssection locations
        shapefile_path: path to a shapefile with a polygon of the area to be selected

    Returns:
        selected_crosssection_locations: GeoDataFrame of the selected crosssection locations
    """
    shapefile_area = gpd.read_file(shapefile_path)
    selected_crosssection_locations = gpd.clip(crosssection_locations, shapefile_area)
    selected_crosssection_locations.rename(columns={'cross_loc_geom': 'geometry'}, inplace=True)
    return selected_crosssection_locations[['branchid', 'definitionid', 'geometry']]

def yz_to_xyz(branches, branch_id, chainage, crs_def_id, crs_def_df):
    # select the branch
    # check chainage to choose baseline_start & end
    branches = branches.set_index('branchid')
    branch = branches.loc[branch_id]
    if branch.geometry.length > chainage + 0.1:
        baseline_end = chainage + 0.1
    elif branch.geometry.length > chainage + 0.05:
        baseline_end = chainage + 0.05
    else:
        raise ValueError("I don't know what to do here yet")

    baseline_start = branch.geometry.interpolate(chainage)
    baseline_end = branch.geometry.interpolate(baseline_end)
    baseline = LineString([baseline_start, baseline_end])

    def_df = crs_def_df.set_index('id')
    def_df = def_df[def_df["type"] == "yz"].copy()
    if crs_def_id in def_df.index:
        y_coords = def_df.loc[crs_def_id, 'ycoordinates']
        z_coords = def_df.loc[crs_def_id, 'zcoordinates']
        nr = def_df.loc[crs_def_id, 'yzcount']
        thalweg = def_df.loc[crs_def_id, 'thalweg']

        line_list = []
        for i in range(int(nr)):
            y = y_coords[i]
            z = z_coords[i]
            if y < thalweg:
                side = 'left'
            else:
                side = 'right'
            side_line = baseline.parallel_offset(abs(y - thalweg), side)
            line_list.append(Point(side_line.coords[0][0], side_line.coords[0][1], z))

        # left_inner = baseline.parallel_offset(bottom_width/2, 'left')
        # right_inner = baseline.parallel_offset(bottom_width/2, 'right')
        # left_inner_point = shapely.ops.transform(lambda x, y: (x, y, bottom_level), Point(left_inner.coords[0]))
        # right_inner_point = shapely.ops.transform(lambda x, y: (x, y, bottom_level), Point(right_inner.coords[-1]))
        #
        # left_outer = baseline.parallel_offset(total_width/2, 'left')
        # right_outer = baseline.parallel_offset(total_width/2, 'right')
        # left_outer_point = shapely.ops.transform(lambda x, y: (x, y, upper_level), Point(left_outer.coords[0]))
        # right_outer_point = shapely.ops.transform(lambda x, y: (x, y, upper_level), Point(right_outer.coords[-1]))

        profile_line = LineString(line_list)
        return profile_line
    else:
        return None



if __name__ == '__main__':
    test_folder = Path(r'D:/local/profile_optimizer/dflowfm')
    net_nc = test_folder/'FlowFM_net.nc'
    br = create_branches(net_nc)
    ini = test_folder/r'crsloc.ini'
    cr = create_crosssections(br, ini, test_folder)
    fn_shp = test_folder/'selection.gpkg'
    select = select_crosssection_locations(cr, fn_shp)
    # print(select.head())
