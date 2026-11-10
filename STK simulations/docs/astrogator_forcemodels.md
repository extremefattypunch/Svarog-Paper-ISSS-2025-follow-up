# STK Astrogator numerical propagator + force models — probe #2

## Relevant enums (stkobjects)
- enum `AgEComponentType`: NOT FOUND
- enum `AgEVAElementType`: NOT FOUND
- enum `AgESrpModel`: NOT FOUND
- enum `AgESRPModel` (20): as_integer_ratio=<method 'as_integer_ratio' of 'int' objects>, bit_count=<method 'bit_count' of 'int' objects>, bit_length=<method 'bit_length' of 'int' objects>, conjugate=<method 'conjugate' of 'int' objects>, denominator=<attribute 'denominator' of 'int' objects>, eSRPModelGPS_BlkIIA_AeroT20=0, eSRPModelGPS_BlkIIA_GSPM04a=1, eSRPModelGPS_BlkIIA_GSPM04ae=2, eSRPModelGPS_BlkIIR_AeroT30=3, eSRPModelGPS_BlkIIR_GSPM04a=4, eSRPModelGPS_BlkIIR_GSPM04ae=5, eSRPModelPlugin=7, eSRPModelSpherical=6, eSRPModelUnknown=-1, from_bytes=<built-in method from_bytes of EnumType object at 0x0000021E9D6D6A60>, imag=<attribute 'imag' of 'int' objects>, is_integer=<method 'is_integer' of 'int' objects>, numerator=<attribute 'numerator' of 'int' objects>, real=<attribute 'real' of 'int' objects>, to_bytes=<method 'to_bytes' of 'int' objects>
- enum `AgEVASRPModel`: NOT FOUND
- enum `AgEVADragModel`: NOT FOUND
- enum `AgEVAAtmosphericModel`: NOT FOUND
- enum `AgEVAShadowModel`: NOT FOUND
- enum `AgEVAStoppingCondition`: NOT FOUND

## ComponentDirectory.GetComponents(int) scan
- GetComponents(0) -> `AgComponentInfoCollection` Count=0 names=[]
- GetComponents(1) -> `AgComponentInfoCollection` Count=0 names=[]
- GetComponents(2) -> `AgComponentInfoCollection` Count=0 names=[]
- GetComponents(3) -> `AgComponentInfoCollection` Count=0 names=[]
- GetComponents(4) -> `AgComponentInfoCollection` Count=0 names=[]

## Initial State: switch to Keplerian
- current ElementType: 0

## Smoke RunMCS with stock propagator
- set Duration.Trip=6000: OK -> `NoneType`
- set Keplerian element fields where present.
- driver.RunMCS(): OK -> `NoneType`
- extract FAIL (AttributeError: 'AgVADriverMCS' object has no attribute 'EphemerisInterval')
