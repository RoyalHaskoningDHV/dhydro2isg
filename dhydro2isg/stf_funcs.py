"""
Standard table format functions
"""
import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import Point, LineString
from dhydro2isg.config import ISG_DTYPES, ISD2_COLUMNS, \
    COL_LINE_ID, IST2_COLUMNS, ISQ2_COLUMNS,\
    ISD2_mapping, ISC2_COLUMNS, LOCATIONS_TYPES, ISQ2_mapping, IST2_mapping, ISG_coupled, IS_1_COLUMNS, \
    CALCULATION_POINTS_COLS, STRUCTURES_COLS, INDEX_COL_STRUCTURES, INDEX_COL_CALCULATION, DISCHARGE_RELATIONS_COLS, \
    INDEX_COL_DISCHARGE, CROSS_SECTIONS_COLS, INDEX_CROSS_SECTIONS, ISG_COLUMNS,INDEX_COL_LOCATIONS, \
    LOCATIONS_TYPE, SEGMENTS_COLS
from dhydro2isg.helper import get_chainage
from dhydro2isg.isc_files import is_left, _coordinate_offset
from datetime import datetime
pd.set_option("mode.chained_assignment", None)


def stf_to_i_1(stf_segments, stf_locations, stf_tab_name, stf_tab, table_type):
    """Create ISD1, ISQ1 and IST1 dataframe from STF
    type: qh, calc or struc
    """
    CNAME = stf_tab.index.get_level_values(0).unique(0).to_list()
    dictOfWords = {i: n for i, n in enumerate(stf_segments.index.values)}
    CNAME = stf_locations.loc[CNAME].sort_values("segment", key=lambda x: x.map(dictOfWords))
    if not CNAME.empty:
        CNAME = CNAME.xs(table_type, level=1, drop_level=False).index.get_level_values(0)
    else:
        CNAME = []
    DIST, N, idx = [], [], []
    for i in range(len(CNAME)):
        geom_pt = stf_locations.loc[(CNAME[i], table_type), "geometry"]
        segment_id = stf_locations.loc[(CNAME[i], table_type), 'segment']
        segment_intersect = stf_segments.loc[segment_id, 'geometry']
        idx.append(segment_id)
        DIST.append(get_chainage(geom_pt, segment_intersect))
        N.append(stf_tab.loc[CNAME[i]].shape[0])

    IREF = np.append(1, np.cumsum(N) + 1)[:-1]

    df_is1 = pd.DataFrame({IS_1_COLUMNS["N"]: N,
                           IS_1_COLUMNS["IREF"]: IREF,
                           IS_1_COLUMNS["DIST"]: DIST,
                           IS_1_COLUMNS["CNAME"]: CNAME}, index=idx)
    df_is1.index.set_names(COL_LINE_ID, inplace=True)
    df_is1 = df_is1.astype(dict(ISG_DTYPES[stf_tab_name]))
    # remove b''

    if any(df_is1.columns == "CNAME"):
        if not df_is1["CNAME"].empty:
            if type(df_is1["CNAME"][0]) == bytes:
                df_is1["CNAME"] = df_is1["CNAME"].str.decode(encoding='latin-1')
                df_is1["CNAME"] = df_is1["CNAME"].apply(lambda x: f'{x: <32}')
    return df_is1


def _create_ISP_single(w_line_single):
    """
    From waterloop to ISP (WITHOUT first 2 non-loc data, and with extra column for segment)
    """
    x, y = w_line_single.geometry.xy
    df_build = pd.DataFrame({"X": x, "Y": y}, index=len(x)*[w_line_single.name])
    df_build = df_build.astype(dict(ISG_DTYPES["ISP"]))
    df_build.index.name = COL_LINE_ID
    return df_build


def stf_to_isp(segments):
    """Create ISP dataframe from STF"""
    ISP = segments.apply(lambda x: _create_ISP_single(x), axis=1)
    return pd.concat(list(ISP))


def stf_to_isd(stf_calcpts, stf_segments, stf_locations):
    """
    Create ISD dataframes from STF
    """
    df_isd1 = stf_to_i_1(stf_segments, stf_locations, "ISD1", stf_tab=stf_calcpts, table_type=LOCATIONS_TYPES['calc'])
    df_isd1.sort_index(inplace=True)

    df_isd2 = stf_calcpts.reset_index()
    if isinstance(df_isd2["datetime"][0], datetime):
        df_isd2['IDATE'] = stf_calcpts.reset_index()['datetime'].apply(lambda x: x.strftime('%Y%m%d'))
    else:
        df_isd2['IDATE'] = df_isd2["datetime"]
    df_isd2.rename(columns=ISD2_mapping, inplace=True)
    df_isd2 = df_isd2[ISD2_COLUMNS.keys()].astype(dict(ISG_DTYPES["ISD2"]))

    return df_isd1, df_isd2


def stf_to_isq(stf_qh, stf_segments, stf_locations):
    """
    Create ISQ dataframes from STF
    """
    df_isq1 = stf_to_i_1(stf_segments, stf_locations, "ISQ1", stf_tab=stf_qh, table_type=LOCATIONS_TYPES['qh'])

    df_isq2 = stf_qh.reset_index()
    df_isq2.rename(columns=ISQ2_mapping, inplace=True)
    df_isq2 = df_isq2[ISQ2_COLUMNS.keys()].astype(dict(ISG_DTYPES["ISQ2"]))

    return df_isq1, df_isq2


def stf_to_ist(stf_struc, stf_segments, stf_locations):
    """
    Create IST dataframes from STF
    """
    if stf_struc.empty:
        print("no structures in dataframe")

    df_ist1 = stf_to_i_1(stf_segments, stf_locations, "IST1", stf_tab=stf_struc, table_type=LOCATIONS_TYPES['struc'])

    df_ist2 = stf_struc.reset_index()
    df_ist2['IDATE'] = stf_struc.reset_index()['datetime'].apply(lambda x: x.strftime('%Y%m%d'))
    df_ist2.rename(columns=IST2_mapping, inplace=True)

    if not df_ist2.empty:
        df_ist2["CTIME"] = df_ist2["datetime"].dt.strftime("%H:%M:%S")
        df_ist2 = df_ist2[IST2_COLUMNS.keys()].astype(dict(ISG_DTYPES["IST2"]))
    else:
        df_ist2["CTIME"] = ""
        df_ist2 = df_ist2[IST2_COLUMNS.keys()].astype(dict(ISG_DTYPES["IST2"]))

    return df_ist1, df_ist2


def stf_to_isc(stf_cross, stf_segments):
    """
    Create ISC dataframes from STF
    """
    # ISC1
    stf_cross = stf_cross[stf_cross["nr_crossings"] == 1]
    stf_cross['nr_coords'] = stf_cross['geometry'].apply(lambda x: len(x.coords))
    stf_cross['intersection_pt'] = stf_cross.apply(
        lambda x: x['geometry'].intersection(stf_segments.loc[x['segment'], 'geometry']), axis=1)
    stf_cross = stf_cross[[type(x) == Point for x in stf_cross['intersection_pt']]]

    stf_cross['chainage'] = stf_cross.apply(
        lambda x: get_chainage(x['intersection_pt'], stf_segments.loc[x['segment'], 'geometry']), axis=1) #reminder: twee intersections? inspecteren!
    stf_cross.dropna(inplace=True)
    idx = stf_cross.loc[:, 'segment'].to_list()
    N = stf_cross['nr_coords'].to_list()
    df_isc1 = pd.DataFrame({IS_1_COLUMNS["N"]: N,
                            IS_1_COLUMNS["IREF"]: np.append(1, np.cumsum(N) + 1)[:-1],
                            IS_1_COLUMNS["DIST"]: stf_cross['chainage'].to_list(),
                            IS_1_COLUMNS["CNAME"]: list(stf_cross.index.values)},
                           index=idx)
    df_isc1["CNAME"] = df_isc1["CNAME"].apply(lambda x: f'{x: <32}')
    df_isc1.index.set_names(COL_LINE_ID, inplace=True)
    df_isc1 = df_isc1.astype(dict(ISG_DTYPES["ISC1"]))

    if any(df_isc1.columns == "CNAME"):
        if type(df_isc1["CNAME"][0]) == bytes:
            df_isc1["CNAME"] = df_isc1["CNAME"].str.decode(encoding='latin-1')

    # ISC2
    distance, bottom, mrc = [], [], []
    for index, row in stf_cross.iterrows():

        cross = row["geometry"]
        segment = stf_segments.loc[row['segment'], 'geometry']

        # change height of z-string so that lowest level is 0
        z_value = [x[2] for x in cross.coords]
        min_zvalue = min(z_value)
        z_value_altered = [x - min_zvalue for x in z_value]

        new_z_string = []
        for z_val, coords_seq in zip(z_value_altered, cross.coords):
            new_z_string.append((coords_seq[0], coords_seq[1], z_val))

        coords = list(LineString(new_z_string).coords)

        # coordinates must be ordered from left to right
        if not is_left(segment, cross.boundary.geoms[0]):
            coords.reverse()
            cross = LineString(coords)

        intersection_chainage = get_chainage(row["intersection_pt"], cross)
        for coor in coords:
            distance.append(get_chainage(Point(coor), cross) - intersection_chainage)
            bottom.append(coor[2])
            mrc.append(row['mrc'])

    df_isc2 = pd.DataFrame({ISC2_COLUMNS["DISTANCE"]: distance,
                            ISC2_COLUMNS["BOTTOM"]: bottom,
                            ISC2_COLUMNS["MRC"]: mrc})

    df_isc2 = df_isc2.astype(dict(ISG_DTYPES["ISC2"]))

    return df_isc1, df_isc2


def get_isg_n_i(i_1):
    """ Get from every i_1 file (ISD1,IST1, ISQ1, ISC1) the number of rows (n) and (i), see documentation """
    i = pd.DataFrame(i_1.iloc[:, 0].groupby(level=0).count())
    i = i.loc[i_1.index.unique()]
    n = pd.DataFrame(np.append(1, np.cumsum(i) + 1)[:-1])
    i.reset_index(inplace=True)
    df = pd.concat([n, i], axis=1, ignore_index=False)
    df.set_index(COL_LINE_ID, inplace=True)
    df.columns = ["n", "i"]
    return df


def stf_to_isg(isp, isd1, isc1, ist1, isq1):
    """
    Create ISG dataframes from STF
    """
    #todo variables from config.py
    buildup_f = (zip(["ISP", "ISD1", "ISC1", "IST1", "ISQ1"], [isp, isd1, isc1, ist1, isq1]))
    isg_cols = []
    for name, tbf_table in buildup_f:
        cols = get_isg_n_i(tbf_table)
        cols.columns = ISG_coupled[name]
        isg_cols.append(cols)

    df = pd.concat(isg_cols, axis=1)
    df[["ISEG", "ICLC", "ICRS", "ISTW", "IQHR"]] = df.loc[:, ["ISEG", "ICLC", "ICRS", "ISTW", "IQHR"]].fillna(
        method='bfill')
    df[["ISEG", "ICLC", "ICRS", "ISTW", "IQHR"]] = df.loc[:, ["ISEG", "ICLC", "ICRS", "ISTW", "IQHR"]].fillna(
        value = df.loc[:, ["ISEG", "ICLC", "ICRS", "ISTW", "IQHR"]].max() + 1)
    df[["ISEG", "ICLC", "ICRS", "ISTW", "IQHR"]] = df.loc[:, ["ISEG", "ICLC", "ICRS", "ISTW", "IQHR"]].fillna(
        method='ffill')
    df[["NSEG", "NCLC", "NCRS", "NSTW", "NQHR"]] = df[["NSEG", "NCLC", "NCRS", "NSTW", "NQHR"]].fillna(0)
    df.index.name = ISG_coupled["index"]
    # if dateframe is empty (like isq when converting from bgt, need to fill na with 0
    df.fillna(0,  inplace=True)
    df = df.astype(dtype=int)
    df.reset_index(inplace=True)
    return df


def isg_to_segments(isg_import):
    """ISG segments to STF"""
    label = []
    segments = []

    for index, row in isg_import.isg_df.iterrows():
        isp_start = int(row[ISG_COLUMNS['ISEG']]) - 1
        isp_end = isp_start + int(row[ISG_COLUMNS['NSEG']])

        points_df = isg_import.isp_df.iloc[isp_start:isp_end]
        points = [Point(xy) for xy in zip(points_df.X, points_df.Y)]
        segments.append(LineString(points))  # Geometry!
        label.append(row[ISG_COLUMNS['LABEL']])

    result = gpd.GeoDataFrame(index=label, geometry=segments)
    result.index.name = 'label'
    result.index.astype(SEGMENTS_COLS['label'])
    # validate length
    if len(result.index) != len(isg_import.isg_df):
        print("Length imported dataframe is not equal to source (ISG). Some records are not imported.")

    return result


def isg_to_locations(isg_import, segments):
    """ISG to locations in stf format"""
    loc_id = []
    loc_type = []
    segment = []
    geometry = []

    # Loop over segments (*.isg)
    for index_isg, row_isg in isg_import.isg_df.iterrows():
        segment_id = row_isg[ISG_COLUMNS['LABEL']]
        segment_geo = segments.loc[segment_id, 'geometry']

        # Loop over calculatons points (*.isd1)
        start_row = int(row_isg[ISG_COLUMNS['ICLC']]) - 1
        end_row = start_row + int(row_isg[ISG_COLUMNS['NCLC']])
        for index, row in isg_import.isd1_df.iloc[start_row: end_row].iterrows():
            loc_id.append(row[IS_1_COLUMNS['CNAME']].strip() + "_" + segment_id)
            loc_type.append(LOCATIONS_TYPE['calc'])
            segment.append(str(segment_id))
            geometry.append(segment_geo.interpolate(float(row[IS_1_COLUMNS['DIST']])))

        # Loop over structures (*.ist1)
        start_row = int(row_isg[ISG_COLUMNS['ISTW']]) - 1
        end_row = start_row + int(row_isg[ISG_COLUMNS['NSTW']])
        for index, row in isg_import.ist1_df.iloc[start_row: end_row].iterrows():
            loc_id.append(row[IS_1_COLUMNS['CNAME']].strip() + "_" + segment_id)
            loc_type.append(LOCATIONS_TYPE['struc'])
            segment.append(str(segment_id))
            geometry.append(segment_geo.interpolate(float(row[IS_1_COLUMNS['DIST']])))

        # Loop over qh locations (*.isq1)
        start_row = int(row_isg[ISG_COLUMNS['IQHR']]) - 1
        end_row = start_row + int(row_isg[ISG_COLUMNS['NQHR']])
        for index, row in isg_import.isq1_df.iloc[start_row: end_row].iterrows():
            loc_id.append(row[IS_1_COLUMNS['CNAME']].strip() + "_" + segment_id)
            loc_type.append(LOCATIONS_TYPE['qh'])
            segment.append(str(segment_id))
            geometry.append(segment_geo.interpolate(float(row[IS_1_COLUMNS['DIST']])))

    df_locations = gpd.GeoDataFrame(
        data={"cname": loc_id, "type": loc_type, "segment": segment}, dtype=str, geometry=geometry)
    df_locations.set_index(INDEX_COL_LOCATIONS, inplace=True)

    return df_locations


def isg_to_calculation_points(isg_import):
    """ISG to discharge relations standard table format"""
    # Load empty cross section geodataframs

    cname = []
    date = []
    wlvl = []
    btml = []
    resis = []
    inff = []

    # Loop over segments (*.isg)
    for index_isg, row_isg in isg_import.isg_df.iterrows():
        start_row = int(row_isg[ISG_COLUMNS['ICLC']]) - 1
        end_row = start_row + int(row_isg[ISG_COLUMNS['NCLC']])

        # Loop over isd1 file
        for index, row in isg_import.isd1_df.iloc[start_row: end_row].iterrows():
            # Create geometry from ist2
            calc_id = row[IS_1_COLUMNS['CNAME']].strip() + "_" + row_isg[ISG_COLUMNS['LABEL']]
            start_row_isd2 = int(row[IS_1_COLUMNS['IREF']]) - 1
            end_row_isd2 = start_row_isd2 + int(row[IS_1_COLUMNS['N']])
            df_isd2 = isg_import.isd2_df.iloc[start_row_isd2:end_row_isd2]

            # add data to lists
            date.extend(df_isd2[ISD2_COLUMNS['IDATE']].to_list())
            wlvl.extend(df_isd2[ISD2_COLUMNS['WLVL']].to_list())
            btml.extend(df_isd2[ISD2_COLUMNS['BTML']].to_list())
            resis.extend(df_isd2[ISD2_COLUMNS['RESIS']].to_list())
            inff.extend(df_isd2[ISD2_COLUMNS['INFF']].to_list())
            cname.extend(len(df_isd2) * [calc_id])

    df_calcpnts = pd.DataFrame(
        data={"cname": cname, "datetime": date, "wlvl": wlvl, "btml": btml, "resis": resis, "inff": inff})
    df_calcpnts = df_calcpnts.astype(CALCULATION_POINTS_COLS)
    df_calcpnts.loc[:, 'datetime'] = pd.to_datetime(df_calcpnts['datetime'], yearfirst=True)
    df_calcpnts.set_index(INDEX_COL_STRUCTURES, inplace=True)

    # validate length
    if len(df_calcpnts.index.levels[0]) != len(isg_import.isd1_df):
        print("Length imported dataframe is not equal to source (ISD1). Some records are not imported.")
    return df_calcpnts


def isg_to_cross_sections(isg_import, segments, locations, calculation_points):
    """ISG to STF cross section format"""
    # Load empty cross section geodataframs
    df_cross_sections = gpd.GeoDataFrame(columns=CROSS_SECTIONS_COLS)
    df_cross_sections.set_index(INDEX_CROSS_SECTIONS, inplace=True)

    # Loop over segments (*.isg)
    for index_isg, row_isg in isg_import.isg_df.iterrows():
        segment_id = row_isg[ISG_COLUMNS['LABEL']]
        segment_geo = segments.loc[segment_id, 'geometry']

        start_row = int(row_isg[ISG_COLUMNS['ICRS']]) - 1
        end_row = start_row + int(row_isg[ISG_COLUMNS['NCRS']])

        # get all calculationpoints on this segment to derive bottomlevel
        # .groupby().mean() is used since btml is assumed to be constant anyway
        locations_in_segment = locations[(locations['segment']==segment_id)].xs('calc',level=1,drop_level=True)
        calculation_in_segment = locations_in_segment.join(calculation_points.groupby('cname').mean())
        # Loop over cross section locations (*.isc1)
        for index, row in isg_import.isc1_df.iloc[start_row: end_row].iterrows():
            # Create geometry from ics2
            start_row_cspt = int(row[IS_1_COLUMNS['IREF']]) - 1
            end_row_cspt = start_row_cspt + int(row[IS_1_COLUMNS['N']])

            pt_cs_on_segment = segment_geo.interpolate(float(row[IS_1_COLUMNS['DIST']]))
            pt_cs_on_segment_direction = segment_geo.interpolate(float(row[IS_1_COLUMNS['DIST']]) + 0.1)

            if len(calculation_in_segment) == 1:
                calculation_in_segment = calculation_in_segment.append(calculation_in_segment, ignore_index=False)

            # Create 3d line of bottomlevel to project cross section on
            bottom_line = LineString([Point(geom.x, geom.y, z) for geom in calculation_in_segment.geometry for
                                      z in calculation_in_segment.btml])
            dist_on_line = bottom_line.project(pt_cs_on_segment)
            projected_cs = bottom_line.interpolate(dist_on_line)

            # Cross section points in ics2 to PointZ geometry
            cs = isg_import.isc2_df.iloc[start_row_cspt:end_row_cspt]
            cs.loc[:, 'coords'] = cs.apply(lambda x:
                                           _coordinate_offset(float(x['DISTANCE']), pt_cs_on_segment.coords[0],
                                                              pt_cs_on_segment_direction.coords[0])[0], axis=1)
            cs.loc[:, 'geometry'] = cs.apply(lambda x: Point(x['coords'][0], x['coords'][1],
                                                             x['BOTTOM']+projected_cs.z), axis=1)

            # Add cross section to df
            cs_id = row[IS_1_COLUMNS['CNAME']].strip()
            if cs_id in df_cross_sections.index:
                cs_id = cs_id + "_" +str(sum(df_cross_sections.index == cs_id))
            df_cross_sections.loc[cs_id, 'segment'] = str(segment_id)
            df_cross_sections.loc[cs_id, 'geometry'] = LineString(cs.sort_values('DISTANCE')['geometry'].to_list())
            df_cross_sections.loc[cs_id, 'mrc'] = cs['MRC'].mean()
            if cs['MRC'].mean() != cs['MRC'].max():
                print(
                    f"Manning value for cross section {cs_id} is averaged to {cs['MRC'].mean()}. The original values are in the range {cs['MRC'].min()} - {cs['MRC'].max()}.")

    # validate length
    if len(df_cross_sections.index) != len(isg_import.isc1_df):
        print("Length imported dataframe is not equal to source (ISC1). Some records are not imported.")

    return df_cross_sections


def isg_to_structures(isg_import):
    """ISG to discharge relations standard table format"""
    # Load empty cross section geodataframs

    cname = []
    date = []
    wlvl_up = []
    wlvl_dwn = []

    # Loop over segments (*.isg)
    for index_isg, row_isg in isg_import.isg_df.iterrows():
        start_row = int(row_isg[ISG_COLUMNS['ISTW']]) - 1
        end_row = start_row + int(row_isg[ISG_COLUMNS['NSTW']])
        # Loop over ist1 file
        for index, row in isg_import.ist1_df.iloc[start_row: end_row].iterrows():
            # Create geometry from ist2
            struc_id = row[IS_1_COLUMNS['CNAME']].strip() + "_" + row_isg[ISG_COLUMNS['LABEL']]
            start_row_ist2 = int(row[IS_1_COLUMNS['IREF']]) - 1
            end_row_ist2 = start_row_ist2 + int(row[IS_1_COLUMNS['N']])
            df_ist2 = isg_import.ist2_df.iloc[start_row_ist2:end_row_ist2]

            # add data to lists
            date.extend(df_ist2[IST2_COLUMNS['IDATE']].to_list())
            wlvl_up.extend(df_ist2[IST2_COLUMNS['WLVL_UP']].to_list())
            wlvl_dwn.extend(df_ist2[IST2_COLUMNS['WLVL_DWN']].to_list())
            cname.extend(len(df_ist2) * [struc_id])

    df_structures = pd.DataFrame(
        data={"cname": cname, "datetime": date, "wlvl_up": wlvl_up, "wlvl_dwn": wlvl_dwn})
    df_structures = df_structures.astype(STRUCTURES_COLS)
    df_structures.loc[:, 'datetime'] = pd.to_datetime(df_structures['datetime'], yearfirst=True)
    df_structures.set_index(INDEX_COL_STRUCTURES, inplace=True)
    # validate length
    if len(df_structures.index.levels[0]) != len(isg_import.ist1_df):
        print("Length imported dataframe is not equal to source (IST1). Some records are not imported.")

    return df_structures


def isg_to_discharge_relations(isg_import):
    """ISG to discharge relations standard table format"""
    # Load empty cross section geodataframs

    cname = []
    q = []
    width = []
    depth = []
    factor = []

    # Loop over segments (*.isg)
    for index_isg, row_isg in isg_import.isg_df.iterrows():
        start_row = int(row_isg[ISG_COLUMNS['IQHR']]) - 1
        end_row = start_row + int(row_isg[ISG_COLUMNS['NQHR']])
        # Loop over qh locations (*.isc1)
        for index, row in isg_import.isq1_df.iloc[start_row: end_row].iterrows():
            # Create geometry from ics2
            qh_id = row[IS_1_COLUMNS['CNAME']].strip() + "_" + row_isg[ISG_COLUMNS['LABEL']]
            start_row_isq2 = int(row[IS_1_COLUMNS['IREF']]) - 1
            end_row_isq2 = start_row_isq2 + int(row[IS_1_COLUMNS['N']])
            df_isq2 = isg_import.isq2_df.iloc[start_row_isq2:end_row_isq2]

            # add data to lists
            q.extend(df_isq2[ISQ2_COLUMNS['Q']].to_list())
            width.extend(df_isq2[ISQ2_COLUMNS['WIDTH']].to_list())
            depth.extend(df_isq2[ISQ2_COLUMNS['DEPTH']].to_list())
            factor.extend(df_isq2[ISQ2_COLUMNS['FACTOR']].to_list())
            cname.extend(len(df_isq2) * [qh_id])

    df_discharge_relations = pd.DataFrame(
        data={"cname": cname, "q": q, "width": width, "depth": depth, "factor": factor})
    df_discharge_relations = df_discharge_relations.astype(DISCHARGE_RELATIONS_COLS)
    df_discharge_relations.set_index(INDEX_COL_DISCHARGE, inplace=True)
    # validate length
    if len(df_discharge_relations.index.levels[0]) != len(isg_import.isq1_df):
        print("Length imported dataframe is not equal to source (ISQ1). Some records are not imported.")

    return df_discharge_relations


def validate_stf(stf):
    valid = True
    valid = min(valid, _validate_calcpts(stf.calculation_points, stf.locations))
    valid = min(valid, _validate_locations(stf.locations,
                                           stf.structures,
                                           stf.discharge_relations,
                                           stf.calculation_points,
                                           stf.segments))
    valid = min(valid, _validate_cross_sections(stf.cross_sections, stf.segments))
    valid = min(valid, _validate_segments(stf.segments))

    if valid:
        print("Validation tables successful")
    return valid


def _validate_segments(segments):
    valid = True
    # Minimal 1 segment
    valid = min(valid, True if len(segments) > 0 else False)
    if not valid:
        print("Error in validation: There must be at least 1 segment")
        return False
    # Labels unique
    valid = min(valid, True if len(segments.index.unique()) == len(segments) else False)
    if not valid:
        print("Error in validation: index values segments are not unique")
        return False
    return valid


def _validate_locations(locations, structures, discharge_relations, calculation_points, segments):
    valid = True

    # Minimal 1 locations
    valid = min(valid, True if len(locations) > 0 else False)
    if not valid:
        print("Error in validation: There must be at least 1 location")
        return False

    # Name Unique
    valid = min(valid, True if len(locations.index.unique()) == len(locations) else False)
    if not valid:
        print("Error in validation: index values locations are not unique")
        return False

    # Every location has a refers to additional data in one of the tables
    valid = min(valid, all(item in list(locations[locations.index.get_level_values(1)==LOCATIONS_TYPES['qh']].index.get_level_values(0)) for item in
                           list(discharge_relations.index.unique(0))))
    valid = min(valid, all(item in list(locations[locations.index.get_level_values(1)==LOCATIONS_TYPES['calc']].index.get_level_values(0)) for item in
                           list(calculation_points.index.unique(0))))
    valid = min(valid, all(item in list(locations[locations.index.get_level_values(1)==LOCATIONS_TYPES['struc']].index.get_level_values(0)) for item in
                           list(structures.index.unique(0))))

    if not valid:
        print("Error in validation: some locations are missing link with data tables")
        return False
    return valid


def _validate_cross_sections(cross_sections, segments):
    valid = True

    # Minimal 1 locations
    valid = min(valid, True if len(cross_sections) > 0 else False)
    if not valid:
        print("Error in validation: There must be at least 1 cross section")
        return False

    # Name Unique
    valid = min(valid, True if len(cross_sections.index.unique()) == len(cross_sections) else False)
    if not valid:
        print("Error in validation: index values cross sections are not unique")
        return False

    # columns mrc has data (no nodata)
    valid = min(valid, min(list(cross_sections['mrc'].notna())))
    if not valid:
        print("Error in validation: column mrc in cross sections contains nodata")
        return False

    # geometry crosses 1 segment (not less or more)
    cross_sections['nr_crossings'] = cross_sections['geometry'].apply(lambda x: sum(segments.intersects(x)))
    if cross_sections['nr_crossings'].min() != 1:
        print(f"Cross sections without segments: {cross_sections[cross_sections['nr_crossings'] == 0]}")
        print(f"Cross sections that intersect with multiple segments: {cross_sections[cross_sections['nr_crossings'] > 1]}")
        #todo check why there crosssections that are not on a segment
        print("these are deleted for now, todo check this out")
        return True
    return valid


def _validate_calcpts(calcpts, locations):
    # Length minimal 1
    valid = True

    valid = min(valid, True if len(calcpts) > 0 else False)
    if not valid:
        print("Error in validation: There must be at least 1 calculation points")
        return False
    # cname unique
    valid = min(valid, True if sum(calcpts.index.duplicated()) == 0 else False)
    if not valid:
        print("Error in validation: index values calculation points are not unique")
        return False
    # cname in locations
    valid = min(valid, True if all(calcpts.index.get_level_values(level=0).unique().isin(locations.index.get_level_values(0))) else False)
    if not valid:
        print("Error in validation: index values calculation points and locations geometry are not consistent")
        return False
    # columns wlvl, btml, resis, inff filled with data (no nodata)
    valid = min(valid, True if all(calcpts[list(CALCULATION_POINTS_COLS.keys())[len(INDEX_COL_CALCULATION):]].notna()) else False)
    if not valid:
        cols_with_na = calcpts.columns[calcpts.isna().any()].tolist()
        print(f'Error in validation: column(s) {cols_with_na} in cross sections contains nodata')
        return False
    return valid


def _validate_structures(structures, locations):
    # Length minimal 1
    valid = True

    valid = min(valid, True if len(structures) > 0 else False)
    if not valid:
        print("Error in validation: There must be at least 1 structure points")
        return False
    # cname unique
    valid = min(valid, True if sum(structures.index.duplicated()) == 0 else False)
    if not valid:
        print("Error in validation: index values structures are not unique")
        return False
    # cname in locations
    valid = min(valid,
                True if all(structures.index.get_level_values(level=0).unique().isin(locations.index.get_level_values(0))) else False)
    if not valid:
        print("Error in validation: index values structures points and locations geometry are not consistent")
        return False

    valid = min(valid, all(structures[list(STRUCTURES_COLS.keys())[len(INDEX_COL_STRUCTURES):]].notna()))
    if not valid:
        cols_with_na = structures.columns[structures.isna().any()].tolist()
        print(f'Error in validation: column(s) {cols_with_na} in cross sections contains nodata')
        return False
    return valid


def _validate_qh(discharge_relations, locations):
    # Length minimal 1
    valid = True

    valid = min(valid, True if len(discharge_relations) > 0 else False)
    if not valid:
        print("Error in validation: There must be at least 1 discharge relation record")
        return False
    # cname unique
    valid = min(valid, True if sum(discharge_relations.index.duplicated()) == 0 else False)
    if not valid:
        print("Error in validation: index values discharge relations are not unique")
        return False
    # cname in locations
    valid = min(valid,
                True if all(
                    discharge_relations.index.get_level_values(level=0).unique().isin(locations.index.get_level_values(0))) else False)
    if not valid:
        print("Error in validation: index values discharge relations and locations geometry are not consistent")
        return False

    valid = min(valid,
                all(discharge_relations[list(DISCHARGE_RELATIONS_COLS.keys())[len(INDEX_COL_DISCHARGE):]].notna()))
    if not valid:
        cols_with_na = discharge_relations.columns[discharge_relations.isna().any()].tolist()
        print(f'Error in validation: column(s) {cols_with_na} in cross sections contains nodata')
        return False
    return valid
