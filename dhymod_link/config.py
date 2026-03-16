import os
import numpy as np
from pyproj import CRS
from tqdm import tqdm
from datetime import date

CRS_28992 = CRS.from_epsg(28992)  #: RD New
CRS_4326 = CRS.from_epsg(4326)  #: WGS84, Default web projection when making interactive plots or dashboards

INTERSECTION_BUFFER = 0.05

ISG_DTYPES = {
    "ISP": [('X', np.single), ('Y', np.single)],
    "ISD1": [('N', np.intc), ('IREF', np.intc), ('DIST', np.single), ('CNAME', np.dtype("S32"))],
    "ISD2": [('IDATE', np.intc), ('WLVL', np.single), ('BTML', np.single), ('RESIS', np.single), ('INFF', np.single)],
    "ISC1": [('N', np.intc), ('IREF', np.intc), ('DIST', np.single), ('CNAME', np.dtype("S32"))],
    "ISC2": [('DISTANCE', np.single), ('BOTTOM', np.single), ('MRC', np.single)],
    "IST1": [('N', np.intc), ('IREF', np.intc), ('DIST', np.single), ('CNAME', np.dtype("S32"))],
    "IST2": [('IDATE', np.intc),  ('WLVL_UP', np.single), ('WLVL_DWN', np.single)],
    "ISQ1": [('N', np.intc), ('IREF', np.intc), ('DIST', np.single), ('CNAME', np.dtype("S32"))],
    "ISQ2": [('Q', np.single), ('WIDTH', np.single), ('DEPTH', np.single), ('FACTOR', np.single)],
}

ISG_HEADERROWS = {
    "ISP": 1,
    "ISD1": 1,
    "ISD2": 1,
    "ISC1": 1,
    "ISC2": 1,
    "IST1": 1,
    "IST2": 1,
    "ISQ1": 1,
    "ISQ2": 1,
}

ISG_RECORDLENGTH = {
    "ISP": 3.216e-42, #2295,
    "ISD1": 11511,
    "ISD2": 5367, # 5367 for ASFR=0, 12535 for ASFR=1
    "ISC1": 11511,
    "ISC2": 4.651e-42, #3319,
    "IST1": 11511,
    "IST2": 3319,
    "ISQ1": 11511,
    "ISQ2": 6.086e-42 #3319,
}

ISG_COLUMNS = {"LABEL": "LABEL",
               "ISEG": "ISEG",
               "NSEG": "NSEG",
               "ICLC": "ICLC",
               "NCLC": "NCLC",
               "ICRS": "ICRS",
               "NCRS": "NCRS",
               "ISTW": "ISTW",
               "NSTW": "NSTW",
               "IQHR": "IQHR",
               "NQHR": "NQHR"}

ISG_coupled = {"index": "LABEL",
               "ISP": ["ISEG", "NSEG"],
               "ISD1": ["ICLC", "NCLC"],
               "ISC1": ["ICRS", "NCRS"],
               "IST1": ["ISTW", "NSTW"],
               "ISQ1": ["IQHR", "NQHR"]}

# Columns that have quotation marks in the binary export
QMARKS_COLUMNS = {"LABEL": "LABEL"}

ISD2_COLUMNS = {"IDATE": "IDATE",
                      "WLVL": "WLVL",
                      "BTML": "BTML",
                      "RESIS": "RESIS",
                      "INFF": "INFF"}

#todo check columns
ISD1_COLUMNS = {"N": "N",
                "IREF": "IREF",
                "DIST": "DIST",
                "CNAME": "CNAME"}

ISP_COLUMNS = ["X", "Y"]
IS_1_COLUMNS = {"N": "N", "IREF": "IREF", "DIST": "DIST", "CNAME": "CNAME"}
ISC2_COLUMNS = {"DISTANCE": "DISTANCE", "BOTTOM": "BOTTOM", "MRC": "MRC"}
ISC1_COLUMNS = {"N": "N", "IREF": "IREF", "DIST": "DIST", "CNAME": "CNAME"}
IST1_COLUMNS = {"N": "N", "IREF": "IREF", "DIST": "DIST", "CNAME": "CNAME"}
#todo check CTIME, is it used by people?. For now CTIME left out
IST2_COLUMNS = {"IDATE": "IDATE", "WLVL_UP": "WLVL_UP", "WLVL_DWN": "WLVL_DWN"}
ISQ1_COLUMNS = {"N": "N", "IREF": "IREF", "DIST": "DIST", "CNAME": "CNAME"}
ISQ2_COLUMNS = {"Q": "Q", "WIDTH": "WIDTH", "DEPTH": "DEPTH", "FACTOR": "FACTOR"}

#todo "SEGMENT_ID", "LINE_ID"
COL_SEGMENT_ID = "SEGMENT_ID"
COL_LINE_ID = "LINE_ID"

LINE_ID = "LINE_ID"
SEGMENT_ID = "SEGMENT_ID"


# COLUMNS SUPRE.PY
SEGMENTS_COLS = {"label": str,
                 "geometry": None}
INDEX_COL_SEGMENTS = "label"

LOCATIONS_COLS = {"cname": str,
                  "type": str,
                  "segment": str,
                  "geometry": None}
INDEX_COL_LOCATIONS = ["cname", "type"]

LOCATIONS_TYPE = {"calc": "calc",
                  "struc": "struc",
                  "qh": "qh"}

COL_PARSE_DATES = ["datetime"]

CALCULATION_POINTS_COLS = {"cname": str,
                           "datetime": str,
                           "wlvl": np.single,
                           "btml": np.single,
                           "resis": np.single,
                           "inff": np.single}
INDEX_COL_CALCULATION = ["cname", 
                         "datetime"
                         ]

CROSS_SECTIONS_COLS = {"cname": str,
                       "mrc": np.single,
                       "segment": str,
                       "geometry": None}
INDEX_CROSS_SECTIONS = ["cname"]

STRUCTURES_COLS = {"cname": str,
                   "datetime": str,
                   "wlvl_up": np.single,
                   "wlvl_dwn": np.single
                   }
INDEX_COL_STRUCTURES = ["cname", "datetime"]

DISCHARGE_RELATIONS_COLS = {"cname": str,
                            "q": np.single,
                            "width": np.single,
                            "depth": np.single,
                            "factor": np.single
                            }
INDEX_COL_DISCHARGE = ["cname", "q"]

# Mapping STF to ISG

ISD2_mapping = {"IDATE": "IDATE", "wlvl": "WLVL", "btml": "BTML", "resis": "RESIS", "inff": "INFF"}
ISQ2_mapping = {"q": "Q", "width": "WIDTH", "depth": "DEPTH", "factor": "FACTOR"}
IST2_mapping = {"IDATE": "IDATE", "ctime": "CTIME", "wlvl_up": "WLVL_UP", "wlvl_dwn": "WLVL_DWN"}

LOCATIONS_TYPES = {"qh": "qh", "calc": "calc", "struc": "struc"}


