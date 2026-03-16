import pandas as pd
import geopandas as gpd
import xarray as xr
from shapely.geometry import LineString, Point
from shapely.errors import ShapelyDeprecationWarning
from pathlib import Path
import warnings

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

def crsloc_ini_to_dataframe(filepath):
    """
    Reads a crsloc.ini file and returns a pandas DataFrame of cross sections, skipping the [General] header.
    """
    cross_sections = []
    current = None
    with open(filepath, 'r', encoding='utf-8') as f:
            in_cross_section = False
            for line in f:
                    line = line.strip()
                    if not line or line.startswith(';'):
                        continue
                    if line.startswith('[General]'):
                        in_cross_section = False
                        continue
                    if line.startswith('[CrossSection]'):
                        if current:
                                cross_sections.append(current)
                        current = {}
                        in_cross_section = True
                        continue
                    if in_cross_section and '=' in line:
                        key, value = map(str.strip, line.split('=', 1))
                        current[key.lower()] = value
            if current:
                    cross_sections.append(current)
    
    return pd.DataFrame(cross_sections)

def crsdef_ini_to_dataframe(filepath):
        # Read the file manually to handle duplicate [Definition] sections
    yz_profiles = []
    with open(filepath, 'r') as f:
        current_section = {}
        in_definition = False
        
        for line in f:
            line = line.strip()
            
            # Check for section header
            if line == '[Definition]':
                # Save previous section if it was a YZ profile
                if in_definition and current_section.get('type') == 'yz':
                    yz_profiles.append(current_section.copy())
                
                # Start new section
                current_section = {}
                in_definition = True
            
            # Parse key-value pairs
            elif in_definition and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip().lower()
                value = value.strip()
                current_section[key] = value
        
        # Don't forget the last section
        if in_definition and current_section.get('type') == 'yz':
            yz_profiles.append(current_section.copy())

    # Create DataFrame
    df_yz_profiles = pd.DataFrame(yz_profiles)
    
    # Convert xcoordinates and ycoordinates from space-separated strings to lists of floats
    if 'zcoordinates' in df_yz_profiles.columns:
        df_yz_profiles['zcoordinates'] = df_yz_profiles['zcoordinates'].apply(
            lambda s: [float(x) for x in s.split()] if isinstance(s, str) else []
        )
    if 'ycoordinates' in df_yz_profiles.columns:
        df_yz_profiles['ycoordinates'] = df_yz_profiles['ycoordinates'].apply(
            lambda s: [float(y) for y in s.split()] if isinstance(s, str) else []
        )

    # Convert numeric columns
    if len(df_yz_profiles) > 0:
        df_yz_profiles['thalweg'] = df_yz_profiles['thalweg'].astype(float)
        df_yz_profiles['yzcount'] = df_yz_profiles['yzcount'].astype(int)
        df_yz_profiles['sectioncount'] = df_yz_profiles['sectioncount'].astype(int)

    # Display the dataframe
    print(f"Found {len(df_yz_profiles)} YZ profiles")
    return df_yz_profiles.drop_duplicates(subset=['id'])

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
    # cross_loc = pd.DataFrame([cs.__dict__ for cs in CrossLocModel(crossloc_source).crosssection])
    cross_loc = crsloc_ini_to_dataframe(crossloc_source)

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
        baseline_end = branch.geometry.length

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
            y = float(y_coords[i])
            z = float(z_coords[i])
            if y < thalweg:
                side = 'left'
            else:
                side = 'right'
            side_line = baseline.parallel_offset(abs(y - thalweg), side)
            line_list.append(Point(side_line.coords[0][0], side_line.coords[0][1], z))

        profile_line = LineString(line_list)
        return profile_line
    else:
        return None

