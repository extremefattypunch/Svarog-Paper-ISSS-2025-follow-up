# STK Astrogator N-Plate SRP/drag configuration — probe #4

## Folders under Astrogator category
- AvailableFolders: OK -> `list`
- folder list failed: 'str' object is not callable; AvailableFolders=['Calculation Objects', 'Central Bodies', 'Constraints', 'Custom Functions', 'Design Tools', 'Engine Models', 'Flight Dynamics Records', 'MCS Segments', 'Power Sources', 'Propagator Functions', 'Propagators', 'Stopping Conditions', 'Thruster Sets']
- astro_cat.GetFolder('Propagators'): OK -> `AgComponentInfoCollection`

### Propagators folder
- type: `AgComponentInfoCollection`
- members: `AvailableFolders`, `Count`, `DuplicateComponent`, `FolderCount`, `FolderName`, `GetFolder`, `GetItemByIndex`, `GetItemByName`, `Item`, `LoadComponent`, `Remove`
- names=Earth J2, Three Body, Heliocentric, Moon HPOP Default v10, Earth Point Mass, Earth Default High Fidelity v13, Cislunar
- DuplicateComponent(default,'SailProp'): OK -> `AgVANumericalPropagatorWrapper`
- props.GetItemByName('SailProp'): OK -> `AgVANumericalPropagatorWrapper`

### numerical propagator SailProp
- type: `AgVANumericalPropagatorWrapper`
- members: `CentralBodyName`, `CloneObject`, `Description`, `Export`, `ExportWithFilenamePath`, `IsReadOnly`, `Name`, `NumericalIntegrator`, `NumericalIntegratorType`, `PropagatorFunctions`, `RegularizedTimeExponent`, `RegularizedTimeStepsPerOrbit`, `SetNumericalIntegrator`, `UseRegularizedTime`, `UseVariationOfParameters`, `UserComment`
- prop.PropagatorFunctions: OK -> `AgVAPropagatorFunctionCollection`

## Force models in default propagator
  - [0] Name=`Gravitational Force` pytype=`AgVAGravityFieldFunction`
  - [1] Name=`Jacchia-Roberts` pytype=`AgVAJacchiaRoberts`
  - [2] Name=`Spherical SRP` pytype=`AgVASRPSpherical`
  - [3] Name=`Moon` pytype=`AgVAThirdBodyFunction`
  - [4] Name=`Sun` pytype=`AgVAThirdBodyFunction`

### force[0] Gravitational Force
- type: `AgVAGravityFieldFunction`
- members: `CentralBodyName`, `CloneObject`, `Degree`, `Description`, `Export`, `ExportWithFilenamePath`, `GravityFilename`, `IncludeTimeDependentSolidTides`, `IsReadOnly`, `MaxDegreeText`, `MaxOrderText`, `MaxPartialsDegreeText`, `MaxPartialsOrderText`, `MinRadiusPercent`, `Name`, `OceanTideMaxDegree`, `OceanTideMaxOrder`, `OceanTideMinAmp`, `Order`, `PartialsDegree`, `PartialsOrder`, `SolidTideMinAmp`, `SolidTideType`, `TruncateSolidTides`, `UseOceanTides`, `UseSecularVariations`, `UserComment`

### force[1] Jacchia-Roberts
- type: `AgVAJacchiaRoberts`
- members: `AtmosDataFilename`, `AtmosDataGeoMagneticFluxSource`, `AtmosDataGeoMagneticFluxUpdateRate`, `AtmosDataSource`, `CloneObject`, `ComputesPressure`, `ComputesTemperature`, `Description`, `DragCorrectionType`, `DragModelPlugin`, `DragModelPluginName`, `DragModelType`, `Export`, `ExportWithFilenamePath`, `F10p7`, `F10p7Avg`, `IsReadOnly`, `Kp`, `NPlateDefinitionFile`, `NPlateStochasticParameters`, `Name`, `StochasticBallisticCoefficient`, `StochasticDensityCorrection`, `SunPosition`, `UseApproximateAltitude`, `UseStochasticBallisticCoeff`, `UseStochasticDensityCorrection`, `UserComment`, `VariableAreaHistoryFile`

### force[2] Spherical SRP
- type: `AgVASRPSpherical`
- members: `AtmosAlt`, `CloneObject`, `Description`, `EclipsingBodies`, `Export`, `ExportWithFilenamePath`, `IncludeBoundaryMitigation`, `IsReadOnly`, `Luminosity`, `MeanFlux`, `Name`, `SRPCorrectionType`, `ShadowModel`, `SolarForceMethod`, `SolarRadius`, `StochasticSRPCoefficient`, `SunPosition`, `UseStochasticSRPCoeff`, `UseSunCbFileValues`, `UserComment`

### force[3] Moon
- type: `AgVAThirdBodyFunction`
- members: `CloneObject`, `Description`, `EphemSource`, `EphemerisSourceWarning`, `Export`, `ExportWithFilenamePath`, `IsReadOnly`, `Mode`, `ModeType`, `Name`, `SetModeType`, `ThirdBodyName`, `UserComment`

### force[4] Sun
- type: `AgVAThirdBodyFunction`
- members: `CloneObject`, `Description`, `EphemSource`, `EphemerisSourceWarning`, `Export`, `ExportWithFilenamePath`, `IsReadOnly`, `Mode`, `ModeType`, `Name`, `SetModeType`, `ThirdBodyName`, `UserComment`

## Class-level member dump: AgVASRPNPlate / AgVANPlateStochasticParam
- `AgVASRPNPlate` members: AtmosAlt, CloneObject, Description, EclipsingBodies, Export, ExportWithFilenamePath, IncludeBoundaryMitigation, IsReadOnly, Luminosity, MeanFlux, NPlateDefinitionFile, NPlateStochasticParameters, Name, ShadowModel, SolarForceMethod, SolarRadius, SunPosition, UseStochasticSRPCoeff, UseSunCbFileValues, UserComment
- `IAgVASRPNPlate` members: AtmosAlt, EclipsingBodies, IncludeBoundaryMitigation, Luminosity, MeanFlux, NPlateDefinitionFile, NPlateStochasticParameters, ShadowModel, SolarForceMethod, SolarRadius, SunPosition, UseStochasticSRPCoeff, UseSunCbFileValues
- `AgVANPlateStochasticParam` members: EstimateParameter, HalfLife, LongTermSigma, Name, NominalValue, Sigma
