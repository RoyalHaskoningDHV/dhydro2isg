# Description 
Dhydro2ISG is a Python package that can extract data from a D-Hydro model to input for a groundwater model in ISG format.  

The base of this script is developed by Haskoning for Waterschap Brabantse Delta. This is further developed by waterschap Aa & Maas. In 2025 this tool is made open source with financial support of waterboard De Dommel. 

# Functionality
- Export a DHydro model to ISG format. Supports segments, cross sections, waterlevel at calculation points (time series)
- Read DHydro format and ISG format into a standardized format (STF). This standardized data can be edited with GIS and exported to ISG. 

# ISG Support
The tool creates an ISG file without support for surface-flow routing (ASFR=0). This ISG file contains the following parameters:

| Parameter       | Description                                                            | Source |
|-------------|------------------------------------------------------------------------|-----|
| Water level | The water level at the calculation node for defined period                               | D-Hydro model |
| Bottom level| The bottom level at the calculation node                               | D-Hydro model |
| Resistance  | The resistance of the river bed at the calculation node (days)                                | Manual input |
| Inf.factor  | The infiltration factor at the calculation node (-)                       | Manual input |
| mrc  | Manning’s Resistance Coefficient MRC for the cross-section (-)                       | Manual input |
 

Q-H relationships and structures are not supported. 


# Notes
Note that the code is tested for a limited amount of D-Hydro models and therefore it is required to validate the output before using it. The code is tested for D-Hydro versions XX, XX, 2025.01 and 2025.03. 

The package is open-source so if you miss functionality you can create a new branch on github and propose a solution. If you experience a bug you can create an issue in github and preferable also propose a solution.  

This tool depends on hydrolib-core. If the model version is not supported by hydrolib core this could raise an error. This is a known issue.


# Usage
* Install in your Python enviroment using pip: `pip install dhydro2isg`
* In the repo you can find an notebook with an example: https://github.com/RoyalHaskoningDHV/dhydro2isg/examples . This folder contains a notebook that demonstrates the workflow of reading an DHydro model and exporting it to ISG. 

# Changelog

### Version 0.3.3 
- Tool published open source under GPL v3 licence
- Added support for installation via pip
- Added example notebooks as documentation
- Changed environment file to pyproject.toml and update dependencies. 
- Changed method to aggragate the value of waterlevels in the defined period

### Version 0.2.0 
In december 2023, Waterschap Aa en Maas receiced this package and developed it further, making the following updates:
- update environment, using a more recent version of hydrolib-core 
    - as an effect, a higher Python version is also possible, but < 3.12
    - all code has been updated to work with python 3.11.6
    - pydantic = 1.10 was required for hydrolib-core to work properly
    - new environment file: `environment - new HL.yml`
- change the way calculation points are snapped to a waterline. 
    - old method used ckdnearest, between the calculation point and the vertex-points of the waterlines. This causes mis-matches when a waterline has very few vertexed. e.g. a canal has very few vertexes because it is very straight. 
    - newly added method: buffer the point and apply a sjoin. This method relies on the geography of the whole line, not just the vertex points. During development, we feared that a buffer + sjoin would be much slower, but for the test model (roughly 25 x 15 km large), the old way took 2 minutes, 8 seconds, whereas the new way takes 2 minutes, 18 seconds. This is not a significant increase in runtime. 
    - this change is implemented in top_flow/dhydro.py. The new function is defined in the top of that document. The practical implementation is done in the function `dhydro_to_stf`. One of the first lines in `dhydro_to_stf`: 
```
    # map_with_network = ckdnearest(map_gdf, net_gdf)
    map_with_network = sjoin_map_with_net(map_gdf, net_gdf)
```
- add option for aggregation in a window at the end of a calculation. 
    - previously, the resulting IPF was based on waterlevel of the final timestep. 
    - now, a window is chosen (e.g. "1D" for final 1 day of the DHydro calculation)
    - then, an aggregation is chosen (e.g. "mean" or "min")
    - this addition is a large improvement for DHydro models with instabilities or fluctuations, for example at pump stations. 
    - defaults: 1 day window & mean for aggregation method. 



# Contact information

### Product owner
* toine.kerckhoffs@haskoning.com

### Developers
* jouke.verstappen@haskoning.com
* jolijn.hiemstra@haskoning.com
* jeroen.winkelhorst@haskoning.com
* lisette.avis@haskoning.com
* eline.steinbusch@haskoning.com
* lweijers@aaenmaas.nl
