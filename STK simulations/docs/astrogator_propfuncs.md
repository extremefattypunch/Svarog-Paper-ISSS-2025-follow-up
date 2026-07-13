# STK Astrogator numerical propagator + force models — probe #3
- enum `AgEVADragModelType`: eVADragModelTypeSpherical=0, eVADragModelTypePlugin=1, eVADragModelTypeVariableArea=2, eVADragModelTypeNPlate=3
- enum `AgEVADragCorrectionType`: eVADragCorrectionTypeBallisticCoeffRelative=0, eVADragCorrectionTypeBallisticCoeffAdditive=1, eVADragCorrectionTypeCdRelative=2, eVADragCorrectionTypeCdAdditive=3

## Component directory navigation
- cd.GetComponents(eComponentAstrogator=2): OK -> `AgComponentInfoCollection` = `<agi.stk13.stkobjects.AgComponentInfoCollection object at 0x000001A67AA8D370>`

### astro component category
- type: `AgComponentInfoCollection`
- members: `AvailableFolders`, `Count`, `DuplicateComponent`, `FolderCount`, `FolderName`, `GetFolder`, `GetItemByIndex`, `GetItemByName`, `Item`, `LoadComponent`, `Remove`
- astro_cat.GetComponents('Propagators'): FAIL (AttributeError: 'AgComponentInfoCollection' object has no attribute 'GetComponents')

## Initial State spacecraft parameters
- initseg.SpacecraftParameters: OK -> `AgVASpacecraftParameters` = `<agi.stk13.stkobjects.astrogator.AgVASpacecraftParameters object at 0x000001A67A`

### SpacecraftParameters
- type: `AgVASpacecraftParameters`
- members: `Cd`, `Ck`, `Cr`, `DragArea`, `DryMass`, `K1`, `K2`, `ProvideRuntimeTypeInfo`, `RadiationPressureArea`, `SolarRadiationPressureArea`
