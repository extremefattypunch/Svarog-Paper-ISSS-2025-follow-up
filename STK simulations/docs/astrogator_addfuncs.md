# STK Astrogator: add/remove force functions + atmosphere templates — probe #5
- astro_cat.GetFolder('Propagator Functions'): OK -> `AgComponentInfoCollection`

### Propagator Functions folder
- type: `AgComponentInfoCollection`
- members: `AvailableFolders`, `Count`, `DuplicateComponent`, `FolderCount`, `FolderName`, `GetFolder`, `GetItemByIndex`, `GetItemByName`, `Item`, `LoadComponent`, `Remove`
- FolderCount=5; folders=['Atmospheric Models', 'Gravity Models', 'Plugins', 'SRP Models', 'Third Bodies']
- Count=4; names=Yarkovsky Effect, Radiation Pressure, State Transition Matrix, General Relativity
  - subfolder `Atmospheric Models`: ['DTM 2012', 'Python Density Model', 'US Standard Atmosphere', 'Mars GRAM 2000', 'Mars GRAM 3 7', 'Mars GRAM 2010', 'Exponential - Mars', 'Exponential - Venus', 'Exponential - Jupiter', 'Mars GRAM 2005', 'Cira72', 'Jacchia Bowman 2008', 'Mars GRAM 2001', 'Jacchia 1970', 'Blended Density', 'Venus GRAM 2005', 'Jacchia 1971', 'DTM 2020', 'Harris-Priester', 'MSISE 1990', 'Exponential - Earth', 'MSIS 1986', 'NRLMSISE 2000', 'Jacchia 1960', 'Jacchia-Roberts', 'Exponential']
  - subfolder `Gravity Models`: ['TwoBody Force', 'Gravitational Force', 'CR3BP Force']
  - subfolder `Plugins`: ['Python HPOP', 'Astrogator Script Driver', 'Python EOM Func', 'HPOP Plugin Example']
  - subfolder `SRP Models`: ['GSPM 04ae-IIA SRP', 'AeroT20 SRP', 'Spherical SRP', 'Python Light Reflection', 'NPlate SRP', 'TabAreaVector SRP', 'GSPM 04a-IIA SRP', 'VariableArea SRP', 'AeroT30 SRP', 'GSPM 04a-IIR SRP', 'GSPM 04ae-IIR SRP']
  - subfolder `Third Bodies`: ['Jupiter System', 'Pluto System', 'Ganymede', 'Jupiter', 'Pluto', 'Neptune System', 'Triton', 'Callisto', 'Neptune', 'Iapetus', 'Phobos', 'Europa', 'Phoebe', 'Deimos', 'Ceres', 'Ariel', 'Io', 'Uranus', 'AsteroidTemplate', 'Moon', 'Charon', 'Titan', 'Rhea', 'Sun', 'Mimas', 'Mercury', 'Mars', 'Titania', 'Hyperion', 'Earth', 'Venus', 'Uranus System', 'Saturn System', 'Saturn', 'Earth-Moon System', 'Dione', 'Tethys', 'Enceladus', 'Vesta']

### PropagatorFunctions collection
- type: `AgVAPropagatorFunctionCollection`
- members: `Add`, `Count`, `Cut`, `GetItemByIndex`, `GetItemByName`, `InsertCopy`, `Item`, `Paste`, `Remove`, `RemoveAll`

### drag function (default)
- type: `AgVAJacchiaRoberts`
- members: `AtmosDataFilename`, `AtmosDataGeoMagneticFluxSource`, `AtmosDataGeoMagneticFluxUpdateRate`, `AtmosDataSource`, `CloneObject`, `ComputesPressure`, `ComputesTemperature`, `Description`, `DragCorrectionType`, `DragModelPlugin`, `DragModelPluginName`, `DragModelType`, `Export`, `ExportWithFilenamePath`, `F10p7`, `F10p7Avg`, `IsReadOnly`, `Kp`, `NPlateDefinitionFile`, `NPlateStochasticParameters`, `Name`, `StochasticBallisticCoefficient`, `StochasticDensityCorrection`, `SunPosition`, `UseApproximateAltitude`, `UseStochasticBallisticCoeff`, `UseStochasticDensityCorrection`, `UserComment`, `VariableAreaHistoryFile`
- drag.DragModelType: OK -> `AgEVADragModelType`
- drag.UseApproximateAltitude: OK -> `bool`
- drag.DragCorrectionType: OK -> `AgEVADragCorrectionType`
- co-rotation candidates on drag: 

## Add() attempts
- pf.Add('AtmosphericDensity',): FAIL (RuntimeError: Error occurred while adding an item.)
- pf.Add('Drag',): FAIL (RuntimeError: Error occurred while adding an item.)
- pf.Add('1976 Standard',): FAIL (RuntimeError: Error occurred while adding an item.)
- pf.Add('Atmospheric Density',): FAIL (RuntimeError: Error occurred while adding an item.)
- pf.Add doc: Adds a function to the collection.

## Rotating-atmosphere search (central body / scenario)
- scen rotat/wind members: 
