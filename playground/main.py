import sys
from top_flow.dhydro import dhydro_to_stf as read_dhydro
from pathlib import Path


base_folder = Path(r"c:/Python/dhydro_to_isg")
input_folder = base_folder/"input"/"20231203_gemwinAD"/"dflowfm"

output_folder = base_folder/"output_test"
output_name = "mean_1D"

wip_folder = base_folder/'WIP'
wip_folder.mkdir(exist_ok=True, parents=True)

dhydro_network_nc = input_folder/'FlowFM_net.nc'
dhydro_map_nc = input_folder/'output'/'FlowFM_map.nc'
crossloc_ini = input_folder/'crsloc.ini'
crossdef_ini = input_folder/'crsdef.ini'

start_time = "2018-01-01"
end_time = "2018-01-03"

resistance = 1
infiltration = 0.3
mrc = 25

aggr_method = "mean"
aggr_window = "1D"

stf = read_dhydro(dhydro_network_nc=dhydro_network_nc,
                  dhydro_map_nc=dhydro_map_nc,
                  crossloc_ini=crossloc_ini,
                  crossdef_ini=crossdef_ini,
                  output_name=output_name,
                  start_time=start_time,
                  end_time=end_time,
                  resistance=resistance,
                  infiltration=infiltration,
                  mrc=mrc,
                  epsg=28992,
                  output_folder=wip_folder,
                  aggregation_window=aggr_window, 
                  aggregation_method=aggr_method)
stf.export_to_text(export_folder=str(output_folder), filename=output_name)
stf.export_to_isg(export_folder=str(output_folder), filename=output_name)