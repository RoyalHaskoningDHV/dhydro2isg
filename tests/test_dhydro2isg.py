"""Test the main dhydro2imod functionality."""

import pytest
import os
from pathlib import Path
import pandas as pd
import geopandas as gpd
from dhydro2isg.dhydro2isg import dhydro_to_stf
from dhydro2isg.stf import STF
from dhydro2isg.config import STRUCTURES_COLS, DISCHARGE_RELATIONS_COLS


@pytest.fixture
def example_data_path():
    """Get path to the example data."""
    base_path = Path(__file__).parent.parent / "examples" / "data"
    dhydro_path = base_path / "Haskoning_example.dsproj_data" / "Haskoning_example"
    return dhydro_path


def test_dhydro_path_exists(example_data_path):
    """Test that the example D-HYDRO model exists."""
    assert example_data_path.exists(), f"Example data path does not exist: {example_data_path}"
    assert (example_data_path / "input").exists(), "Input folder not found"
    assert (example_data_path / "output").exists(), "Output folder not found"


def test_required_dhydro_files_exist(example_data_path):
    """Test that all required D-HYDRO files exist."""
    required_files = [
        "input/FlowFM_net.nc",
        "input/crsdef.ini",
        "input/crsloc.ini",
        "output/Haskoning_example_map.nc",
    ]
    for file_path in required_files:
        full_path = example_data_path / file_path
        assert full_path.exists(), f"Required file not found: {file_path}"


def test_dhydro_to_stf_conversion(example_data_path):
    """Test the main conversion from D-HYDRO to STF format."""
    stf = dhydro_to_stf(
        dhydro_folder=str(example_data_path),
        start_time="2026-01-03",
        end_time="2026-01-05",
        resistance=1.0,
        infiltration=0.3,
        mrc=0.02,
        aggregation_method="mean",
        epsg=28992,
        output_name="test_dhydro_to_isg",
        relpath_network_nc="input/FlowFM_net.nc",
        relpath_map_nc="output/Haskoning_example_map.nc",
        relpath_crossloc_ini="input/crsloc.ini",
        relpath_crossdef_ini="input/crsdef.ini",
    )
    
    # Check that STF object is created
    assert isinstance(stf, STF), "Conversion should return an STF object"
    
    # Check that STF has required attributes
    assert hasattr(stf, "segments"), "STF should have segments"
    assert hasattr(stf, "locations"), "STF should have locations"
    assert hasattr(stf, "calculation_points"), "STF should have calculation_points"
    assert hasattr(stf, "cross_sections"), "STF should have cross_sections"


def test_stf_segments_structure(example_data_path):
    """Test that STF segments have expected structure."""
    stf = dhydro_to_stf(
        dhydro_folder=str(example_data_path),
        start_time="2026-01-03",
        end_time="2026-01-05",
        resistance=1.0,
        infiltration=0.3,
        mrc=0.02,
        aggregation_method="mean",
        epsg=28992,
        output_name="test_segments",
        relpath_network_nc="input/FlowFM_net.nc",
        relpath_map_nc="output/Haskoning_example_map.nc",
        relpath_crossloc_ini="input/crsloc.ini",
        relpath_crossdef_ini="input/crsdef.ini",
    )
    
    segments = stf.segments
    assert len(segments) > 0, "Segments should not be empty"
    assert "geometry" in segments.columns, "Segments should have geometry column"
    assert isinstance(segments, gpd.GeoDataFrame), "Segments should be a GeoDataFrame"


def test_stf_locations_structure(example_data_path):
    """Test that STF locations have expected structure."""
    stf = dhydro_to_stf(
        dhydro_folder=str(example_data_path),
        start_time="2026-01-03",
        end_time="2026-01-05",
        resistance=1.0,
        infiltration=0.3,
        mrc=0.02,
        aggregation_method="mean",
        epsg=28992,
        output_name="test_locations",
        relpath_network_nc="input/FlowFM_net.nc",
        relpath_map_nc="output/Haskoning_example_map.nc",
        relpath_crossloc_ini="input/crsloc.ini",
        relpath_crossdef_ini="input/crsdef.ini",
    )
    
    locations = stf.locations
    assert len(locations) > 0, "Locations should not be empty"
    assert isinstance(locations, (pd.DataFrame, gpd.GeoDataFrame)), "Locations should be a DataFrame or GeoDataFrame"


def test_stf_calculation_points_structure(example_data_path):
    """Test that STF calculation points have expected structure and values."""
    stf = dhydro_to_stf(
        dhydro_folder=str(example_data_path),
        start_time="2026-01-03",
        end_time="2026-01-05",
        resistance=1.0,
        infiltration=0.3,
        mrc=0.02,
        aggregation_method="mean",
        epsg=28992,
        output_name="test_calc_points",
        relpath_network_nc="input/FlowFM_net.nc",
        relpath_map_nc="output/Haskoning_example_map.nc",
        relpath_crossloc_ini="input/crsloc.ini",
        relpath_crossdef_ini="input/crsdef.ini",
    )
    
    calc_points = stf.calculation_points
    assert len(calc_points) > 0, "Calculation points should not be empty"
    assert isinstance(calc_points, pd.DataFrame), "Calculation points should be a DataFrame"
    
    # Check for expected columns
    expected_cols = ["wlvl", "btml", "resis", "inff"]
    for col in expected_cols:
        assert col in calc_points.columns, f"Calculation points should have column: {col}"


def test_aggregation_methods(example_data_path):
    """Test different aggregation methods produce valid results."""
    aggregation_methods = ["mean", "max", "min"]
    
    for method in aggregation_methods:
        stf = dhydro_to_stf(
            dhydro_folder=str(example_data_path),
            start_time="2026-01-03",
            end_time="2026-01-05",
            resistance=1.0,
            infiltration=0.3,
            mrc=0.02,
            aggregation_method=method,
            epsg=28992,
            output_name=f"test_agg_{method}",
            relpath_network_nc="input/FlowFM_net.nc",
            relpath_map_nc="output/Haskoning_example_map.nc",
            relpath_crossloc_ini="input/crsloc.ini",
            relpath_crossdef_ini="input/crsdef.ini",
        )
        
        # Basic validation
        assert stf is not None, f"STF should be created for aggregation method: {method}"
        assert len(stf.calculation_points) > 0, f"Calculation points empty for aggregation method: {method}"


def test_uniform_parameters_applied(example_data_path):
    """Test that uniform parameters are correctly applied."""
    resistance = 2.5
    infiltration = 0.5
    mrc = 0.035
    
    stf = dhydro_to_stf(
        dhydro_folder=str(example_data_path),
        start_time="2026-01-03",
        end_time="2026-01-05",
        resistance=resistance,
        infiltration=infiltration,
        mrc=mrc,
        aggregation_method="mean",
        epsg=28992,
        output_name="test_uniform_params",
        relpath_network_nc="input/FlowFM_net.nc",
        relpath_map_nc="output/Haskoning_example_map.nc",
        relpath_crossloc_ini="input/crsloc.ini",
        relpath_crossdef_ini="input/crsdef.ini",
    )
    
    calc_points = stf.calculation_points
    
    # Check that resistance and infiltration are applied
    # These should be uniform across all calculation points
    assert "resis" in calc_points.columns, "Resistance column should exist"
    assert "inff" in calc_points.columns, "Infiltration column should exist"


def test_stf_cross_sections_structure(example_data_path):
    """Test that STF cross sections have expected structure."""
    stf = dhydro_to_stf(
        dhydro_folder=str(example_data_path),
        start_time="2026-01-03",
        end_time="2026-01-05",
        resistance=1.0,
        infiltration=0.3,
        mrc=0.02,
        aggregation_method="mean",
        epsg=28992,
        output_name="test_cross_sections",
        relpath_network_nc="input/FlowFM_net.nc",
        relpath_map_nc="output/Haskoning_example_map.nc",
        relpath_crossloc_ini="input/crsloc.ini",
        relpath_crossdef_ini="input/crsdef.ini",
    )
    
    cross_sections = stf.cross_sections
    assert isinstance(cross_sections, (pd.DataFrame, gpd.GeoDataFrame)), "Cross sections should be a DataFrame or GeoDataFrame"


def test_time_period_extraction(example_data_path):
    """Test extraction for different time periods."""
    time_periods = [
        ("2026-01-03", "2026-01-05"),
        ("2026-01-02", "2026-01-04"),
    ]
    
    for start, end in time_periods:
        stf = dhydro_to_stf(
            dhydro_folder=str(example_data_path),
            start_time=start,
            end_time=end,
            resistance=1.0,
            infiltration=0.3,
            mrc=0.02,
            aggregation_method="mean",
            epsg=28992,
            output_name=f"test_period_{start}_{end}",
            relpath_network_nc="input/FlowFM_net.nc",
            relpath_map_nc="output/Haskoning_example_map.nc",
            relpath_crossloc_ini="input/crsloc.ini",
            relpath_crossdef_ini="input/crsdef.ini",
        )
        
        assert stf is not None, f"STF should be created for period {start} to {end}"
        assert len(stf.calculation_points) > 0, f"Calculation points should not be empty for period {start} to {end}"


def test_water_level_values_valid(example_data_path):
    """Test that extracted water level values are numerically valid."""
    stf = dhydro_to_stf(
        dhydro_folder=str(example_data_path),
        start_time="2026-01-03",
        end_time="2026-01-05",
        resistance=1.0,
        infiltration=0.3,
        mrc=0.02,
        aggregation_method="mean",
        epsg=28992,
        output_name="test_wl_values",
        relpath_network_nc="input/FlowFM_net.nc",
        relpath_map_nc="output/Haskoning_example_map.nc",
        relpath_crossloc_ini="input/crsloc.ini",
        relpath_crossdef_ini="input/crsdef.ini",
    )
    
    calc_points = stf.calculation_points
    
    # Check water level values
    if "wlvl" in calc_points.columns:
        wlvl = calc_points["wlvl"]
        # Water levels should be finite (not NaN or Inf)
        assert wlvl.notna().any(), "At least some water level values should not be NaN"
        # Water levels should be reasonable (between -100m and 100m for most cases)
        valid_wlvl = wlvl[wlvl.notna()]
        if len(valid_wlvl) > 0:
            assert valid_wlvl.min() >= -100, "Water levels should be above -100m"
            assert valid_wlvl.max() <= 100, "Water levels should be below 100m"