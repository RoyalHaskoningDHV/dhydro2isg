

import pandas as pd
import geopandas as gpd
from dhydro2isg.config import SEGMENTS_COLS, CROSS_SECTIONS_COLS, STRUCTURES_COLS, \
    DISCHARGE_RELATIONS_COLS, INDEX_COL_SEGMENTS, INDEX_COL_LOCATIONS, INDEX_COL_CALCULATION, INDEX_COL_DISCHARGE, \
    INDEX_COL_STRUCTURES, INDEX_CROSS_SECTIONS, COL_PARSE_DATES,LOCATIONS_COLS, CALCULATION_POINTS_COLS
from dhydro2isg.isg import ISG
from dhydro2isg.stf_funcs import validate_stf, isg_to_segments, isg_to_locations, isg_to_structures, \
    isg_to_calculation_points, isg_to_cross_sections, isg_to_discharge_relations
import os
from typing import Optional
from dhydro2isg.helper import seg_overlay

import warnings
warnings.filterwarnings("ignore")


class STF:
    """
    STF is the Topflow Standard Table Format. It saves the top system data as a collection of pandas DataFrames and
    geopandas GeoDataFrames. There are methods to read shapefiles, ISG models or create the data from scratch.
    The STF data can be exported as CSV & Shapefile tables, or as an ISG file suitable for iMOD.
    """
    def __init__(self):
        self._segments = gpd.GeoDataFrame(columns=SEGMENTS_COLS)
        self._locations = gpd.GeoDataFrame(columns=LOCATIONS_COLS)
        self._calculation_points = pd.DataFrame(columns=CALCULATION_POINTS_COLS)
        self._cross_sections = gpd.GeoDataFrame(columns=CROSS_SECTIONS_COLS)
        self._structures = pd.DataFrame(columns=STRUCTURES_COLS)
        self._discharge_relations = pd.DataFrame(columns=DISCHARGE_RELATIONS_COLS)

        self._segments.set_index(INDEX_COL_SEGMENTS, inplace=True)
        self._locations.set_index(INDEX_COL_LOCATIONS, inplace=True)
        self._calculation_points.set_index(INDEX_COL_CALCULATION, inplace=True)
        self._cross_sections.set_index(INDEX_CROSS_SECTIONS, inplace=True)
        self._structures.set_index(INDEX_COL_STRUCTURES, inplace=True)
        self._discharge_relations.set_index(INDEX_COL_DISCHARGE, inplace=True)

    @property
    def segments(self):
        return self._segments

    @property
    def locations(self):
        return self._locations

    @property
    def calculation_points(self):
        return self._calculation_points

    @property
    def cross_sections(self):
        return self._cross_sections

    @property
    def structures(self):
        return self._structures

    @property
    def discharge_relations(self):
        return self._discharge_relations

    def clean_stf(self, minlength: Optional[int] = None):

        if minlength:
            self._segments = self._segments[self._segments.length >= minlength]

        # In Shapely 2.0, len() on geometry objects like MultiPoint raises TypeError.
        # Use boundary.is_empty to keep only segments with non-empty boundaries (i.e., not closed rings).
        self._segments = self._segments[~self._segments.boundary.is_empty]
        
        segment_ids = list(self._segments.index)
        self._locations = self._locations.loc[self._locations["segment"].isin(segment_ids)]

        loc_keep = gpd.sjoin(self._locations, gpd.GeoDataFrame(geometry=self._segments.buffer(0.001)), how="inner")
        loc_keep.dropna(inplace=True)
        loc_keep = loc_keep[~loc_keep.index.duplicated(keep='first')]
        self._locations = loc_keep

        segment_ids = list(self._locations["segment"])

        self._cross_sections = self._cross_sections.loc[self._cross_sections["segment"].isin(segment_ids)]

        self._structures = self._structures.loc[self._structures.index.get_level_values(level=0).isin(self._locations.index.get_level_values(level=0))]
        self._discharge_relations = self._discharge_relations.loc[self._discharge_relations.index.get_level_values(level=0).isin(self._locations.index.get_level_values(level=0))]
        self._calculation_points = self._calculation_points.loc[self._calculation_points.index.get_level_values(level=0).isin(self._locations.index.get_level_values(level=0))]


        print("cleaned STF")

    def import_isg(self, filepath_isg: str):
        """
        This function imports an existing ISG-file. Define the file path and name including the extension *.isg.
        """

        isg_import = ISG()
        isg_import.read_isg(filepath_isg)
        print("Convert ISG to in-memory standard table format")
        print("Note that the tables in memory will be overwritten")
        print("Creating segments geometry..")
        self._segments = isg_to_segments(isg_import)
        print("Creating locations geometry..")
        self._locations = isg_to_locations(isg_import, self._segments)
        print("Creating calculations points table..")
        self._calculation_points = isg_to_calculation_points(isg_import)
        print("Creating cross sections geometry..")
        self._cross_sections = isg_to_cross_sections(isg_import, self._segments,
                                                     self._locations, self._calculation_points)
        print("Creating structures table..")
        self._structures = isg_to_structures(isg_import)
        print("Creating discharge relations table..")
        self._discharge_relations = isg_to_discharge_relations(isg_import)
        print("ISG imported to STF")

    def export_to_isg(self, filename: str, export_folder: str):
        """
        This function transforms the internal standard table format (STF) to an ISG-file and exports it as ISG.
        Define the file name (without extension) and export folder.
        """
        if validate_stf(self):
            isg_export = ISG()
            isg_export.create_from_stf(self)
            os.makedirs(export_folder, exist_ok=True)
            isg_export.export_isg(filename, export_folder)
            print(f"Exported to ISG {export_folder + '/' + filename}")
        else:
            print("Error in validation - ISG not exported")

    def export_to_text(self, filename: str, export_folder: str):
        """
        This function transforms the internal standard table format (STF) to an ISG-file and exports it as ISG.
        Instead of binary files, this function exports all files as text files.
        Define the file name (without extension) and export folder.
        """
        if validate_stf(self):
            isg_export = ISG()
            isg_export.create_from_stf(self)
            isg_export.export_text(filename, export_folder)
            print(f"Exported to ISG {export_folder + '/' + filename}")
        else:
            print("Error in validation - ISG not exported")

    def export_to_shape(self, filename: str, export_folder: str):
        """
        Exports the internal standard table format (STF) to .shp and csv files. Use this function to manually adjust these files (e.g. add, remove or adjust streams or water levels).
        The exported files can be imported with the import_from_shape function. Afterwards, use another export function to transform it to the desired output format.

        """
        os.makedirs(export_folder, exist_ok=True)
        self._segments.reset_index().to_file(os.path.join(export_folder, filename + "_segments.shp"))
        self._locations.reset_index().to_file(os.path.join(export_folder, filename + "_locations.shp"))
        self._calculation_points.reset_index().to_csv(os.path.join(export_folder, filename + "_calculation_points.csv"))
        self._cross_sections.reset_index().astype({'mrc': int}).drop(
            ['intersection_pt'], axis=1, errors='ignore').to_file(os.path.join(export_folder, filename +
                                                                                     "_cross_sections.shp"))
        self._structures.reset_index().to_csv(os.path.join(export_folder, filename + "_structures.csv"))
        self._discharge_relations.reset_index().to_csv(
            os.path.join(export_folder, filename + "_discharge_relations.csv"))
        print("Export completed")

    def import_from_shape(self, import_folder, prefix_filename, suffix_segments="_segments.shp",
                          suffix_locations="_locations.shp", suffix_calculation_points="_calculation_points.csv",
                          suffix_structures="_structures.csv", suffix_qh="_discharge_relations.csv",
                          suffx_cross_sections="_cross_sections.shp"):
        """
        Imports files from shp and csv. The format and the amount of files (which is the standard table format, STF) must be equal to the format and amount of files of the export_to_shape function.
        """
        self._calculation_points = pd.read_csv(
            os.path.join(import_folder, prefix_filename + "" + suffix_calculation_points),
            dtype=CALCULATION_POINTS_COLS,
            parse_dates=COL_PARSE_DATES)
        self._calculation_points = self._calculation_points[list(CALCULATION_POINTS_COLS.keys())]
        self._calculation_points.set_index(INDEX_COL_CALCULATION, inplace=True)

        self._structures = pd.read_csv(os.path.join(import_folder, prefix_filename + "" + suffix_structures),
                                       dtype=STRUCTURES_COLS,
                                       parse_dates=COL_PARSE_DATES)
        self._structures = self._structures[list(STRUCTURES_COLS.keys())]
        self._structures.set_index(INDEX_COL_STRUCTURES, inplace=True)

        self._discharge_relations = pd.read_csv(os.path.join(import_folder, prefix_filename + "" + suffix_qh),
                                                dtype=DISCHARGE_RELATIONS_COLS)
        self._discharge_relations = self._discharge_relations[list(DISCHARGE_RELATIONS_COLS.keys())]
        self._discharge_relations.set_index(INDEX_COL_DISCHARGE, inplace=True)

        self._segments = gpd.read_file(os.path.join(import_folder, prefix_filename + "" + suffix_segments),
                                       dtype=SEGMENTS_COLS)
        self._segments = self._segments[list(SEGMENTS_COLS.keys())]
        self._segments.set_index(INDEX_COL_SEGMENTS, inplace=True)

        self._locations = gpd.read_file(os.path.join(import_folder, prefix_filename + "" + suffix_locations),
                                        dtype=LOCATIONS_COLS)
        self._locations = self._locations[list(LOCATIONS_COLS.keys())]
        self._locations.set_index(INDEX_COL_LOCATIONS, inplace=True)

        self._cross_sections = gpd.read_file(os.path.join(import_folder, prefix_filename + "" + suffx_cross_sections),
                                             dtype=CROSS_SECTIONS_COLS)
        self._cross_sections = self._cross_sections[list(CROSS_SECTIONS_COLS.keys())]
        self._cross_sections.set_index(INDEX_CROSS_SECTIONS, inplace=True)
        print("import succeeded")

    def import_from_gdf(self, segments: gpd.GeoDataFrame, locations: gpd.GeoDataFrame, calculation_points: pd.DataFrame,
                        structures: pd.DataFrame, qh: pd.DataFrame, cross_sections: gpd.GeoDataFrame):
        """
        Imports files from gdf & df. The format and the amount of files (which is the standard table format, STF) must be equal to the format and amount of files of the export_to_shape function.
        """
        self._calculation_points = calculation_points
        self._calculation_points = self._calculation_points[list(CALCULATION_POINTS_COLS.keys())]
        self._calculation_points.set_index(INDEX_COL_CALCULATION, inplace=True)

        self._structures = structures
        self._structures = self._structures[list(STRUCTURES_COLS.keys())]
        self._structures.set_index(INDEX_COL_STRUCTURES, inplace=True)

        self._discharge_relations = qh
        self._discharge_relations = self._discharge_relations[list(DISCHARGE_RELATIONS_COLS.keys())]
        self._discharge_relations.set_index(INDEX_COL_DISCHARGE, inplace=True)

        self._segments = segments
        self._segments = self._segments[list(SEGMENTS_COLS.keys())]
        self._segments.set_index(INDEX_COL_SEGMENTS, inplace=True)

        self._locations = locations
        self._locations = self._locations[list(LOCATIONS_COLS.keys())]
        self._locations.set_index(INDEX_COL_LOCATIONS, inplace=True)

        self._cross_sections = cross_sections
        self._cross_sections = self._cross_sections[list(CROSS_SECTIONS_COLS.keys())]
        self._cross_sections.set_index(INDEX_CROSS_SECTIONS, inplace=True)
        print("import succeeded")


    def mask_double_line(self, mask_stf, bufferdist: int = 10, minlength: Optional[int] = 10,
                         save_deleted: bool = True, save_deleted_folder: Optional[str] = None):
        """
        deletes ISG lines based on a masking ISG file: See seg_overlay
        """

        self._segments = seg_overlay(self._segments, mask_stf._segments, bufferdist=bufferdist, minlength=minlength,
                                     save_deleted=save_deleted, save_deleted_folder=save_deleted_folder)
        print("masked out overlapping lines")


    def validate_stf(self):
        """
        This function checks whether the standard table format is correctly applied.
        """
        return validate_stf(self)







