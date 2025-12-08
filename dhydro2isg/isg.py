import os
from dhydro2isg.readwrite import write_as_text, write_as_binary
from dhydro2isg.stf_funcs import stf_to_isp, stf_to_isd, stf_to_isq, stf_to_ist, stf_to_isc, stf_to_isg
from dhydro2isg.config import ISG_DTYPES
from dhydro2isg.readwrite import read_meta, read_isg_files

class ISG:
    """"
    ISG object, which manages a collection of tables which make up an ISG
    """

    def __init__(self):
        self.path_import = None
        self.fn_import = None
        self._isg_df = None
        self._isg_files = None
        self._isp_df = None
        self._isd1_df = None
        self._isd2_df = None
        self._isc1_df = None
        self._isc2_df = None
        self._ist1_df = None
        self._ist2_df = None
        self._isq1_df = None
        self._isq2_df = None
        self._time_indices = None
        # TODO: add settings dictionary

    def read_isg(self, fn_isg: str):
        """
        Read ISG files
        """
        path = os.path.dirname(fn_isg)
        self.fn_import = os.path.splitext(os.path.basename(path))[0]
        if os.path.exists(path):
            self.path_import = path
        else:
            raise FileNotFoundError

        print(f"Import ISG files from {self.path_import}")
        print(r"Import *.isg file to variable .isg_df")
        print("Note: Dataframes in memory will be overwritten")
        self._isg_df = read_meta(fn_isg)
        self._isg_files = read_isg_files(fn_isg)
        self._isp_df = self._isg_files['ISP']
        self._isd1_df = self._isg_files['ISD1']
        self._isd2_df = self._isg_files['ISD2']
        self._isc1_df = self._isg_files['ISC1']
        self._isc2_df = self._isg_files['ISC2']
        self._ist1_df = self._isg_files['IST1']
        self._ist2_df = self._isg_files['IST2']
        self._isq1_df = self._isg_files['ISQ1']
        self._isq2_df = self._isg_files['ISQ2']

        print("ISG files imported")

    @property
    def isg_df(self):
        return self._isg_df

    @property
    def isp_df(self):
        """Table with geographic information of each line segment"""
        return self._isp_df

    @property
    def filetypes(self):
        return self._isg_files.keys()

    @property
    def isd1_df(self):
        """Table with reference of calculation points to timeseries in isd2 file"""
        return self._isd1_df

    @property
    def isd2_df(self):
        """Table with timeseries of calculation point"""
        return self._isd2_df

    @property
    def isc1_df(self):
        """Table with reference of location of crosssections given in isc2 file"""
        return self._isc1_df

    @property
    def isc2_df(self):
        """Table with cross section information"""
        return self._isc2_df

    @property
    def ist1_df(self):
        """Table with reference of location of structures given in ist2 file"""
        return self._ist1_df

    @property
    def ist2_df(self):
        """Table with timeseries of structures"""
        return self._ist2_df

    @property
    def isq1_df(self):
        """Table with locations with Q width/depth relationships"""
        return self._isq1_df

    @property
    def isq2_df(self):
        """Table with the Q width/depth relationships"""
        return self._isq2_df

    def export_isg(self, filename: str, export_dir: str):
        write_as_text(self.isg_df, filename, "ISG", export_dir)
        for abr in ISG_DTYPES.keys():
            if (eval("self." + str.lower(abr) + "_df")) is not None:
                #if not (eval("self." + str.lower(abr) + "_df")).empty:
                    write_as_binary(eval("self." + str.lower(abr) + "_df"), filename, str.upper(abr), export_dir)
            else:
                print(f"{filename + '.' + abr} file not exported because dataframe is empty")

    def export_text(self, filename: str, export_dir: str):
        write_as_text(self.isg_df, filename, "ISG", export_dir)
        for abr in ISG_DTYPES.keys():
            if (eval("self." + str.lower(abr) + "_df")) is not None:
                write_as_text(eval("self." + str.lower(abr) + "_df"), filename, str.upper(abr), export_dir)
            else:
                print(f"{filename + '.' + abr} file not exported because dataframe is empty")

    def create_from_stf(self, stf):
        """Create ISG from Standard Table Format"""

        self._isp_df = stf_to_isp(stf.segments)
        self._isd1_df, self._isd2_df = stf_to_isd(stf_calcpts=stf.calculation_points, stf_segments=stf.segments, stf_locations=stf.locations)
        self._isc1_df, self._isc2_df = stf_to_isc(stf_cross=stf.cross_sections, stf_segments=stf.segments)
        self._ist1_df, self._ist2_df = stf_to_ist(stf_struc=stf.structures, stf_segments=stf.segments, stf_locations=stf.locations)
        self._isq1_df, self._isq2_df = stf_to_isq(stf_qh=stf.discharge_relations, stf_segments=stf.segments, stf_locations=stf.locations)
        self._isg_df = stf_to_isg(self._isp_df, self._isd1_df, self.isc1_df, self._ist1_df, self._isq1_df)

