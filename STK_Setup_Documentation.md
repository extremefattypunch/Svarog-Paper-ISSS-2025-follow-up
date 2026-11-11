# STK 13 Setup Guide (Ansys Academic Research)

This guide is for a completely new user setting up **Ansys STK 13** with a FlexNet license.

If you are brand new: install **FlexNet server (Ansys License Manager)** first, then configure STK.

## Scope

- STK product: `STK Pro/Premium` (as installed from Ansys downloads)
- Licensing system: `FlexNet Publisher (lmgrd + ansyslmd)`
- Windows host example: `ianpoonWindows`
- Default license port: `1055`

---

## Step 0: Prerequisites

Before starting, make sure you have:

- STK installer ZIP downloaded (for example `Ansys_STK_Premium_ODTK_v13.0.1.zip`)
- Ansys License Manager package available (for example folder `AnsysLicenseManager` with `setup.exe`)
- A generated Ansys license file from the Licensing Portal, e.g.
  - `C:\Users\Ian Poon\Desktop\Ansys_license_1197757_70a8d321e17a.lic`
- Local admin rights (needed for service/Program Files installs)

---

## Step 1 (Required): Configure Ansys Licensing Settings

Open **Ansys Licensing Settings 2025 R2** and set:

- Port: `1055`
- Server 1: `ansysteach.cc.ic.ac.uk`

Then click **Test** and **Save**.

Also download your generated license file and keep it in a known location, preferably:

- `C:\Users\Ian Poon\Desktop\Ansys_license_1197757_70a8d321e17a.lic`

This confirms you can reach the institutional license server and have your own license file available for local hosting.

---

## Step 2: Install FlexNet Server (First-Time User)

This is the part most new users miss. STK cannot use your personal `.lic` file unless a FlexNet server is running.

### 2.1 Open the Ansys License Manager installer

1. Open the folder containing License Manager media:
  - `C:\Users\Ian Poon\Desktop\AnsysLicenseManager`
2. Right-click `setup.exe` and click **Run as administrator**.
3. In the Ansys Installation Launcher, click:
  - **Install Ansys License Manager**
  - Do **not** choose MPI.

### 2.2 Complete the installer screens

On the installer pages:

1. Accept license agreement.
2. Keep default destination path.
3. When asked for license file, browse to:
  - `C:\Users\Ian Poon\Desktop\Ansys_license_1197757_70a8d321e17a.lic`
4. Keep port as `1055`.
5. Finish install.

### 2.3 Confirm server installation succeeded

Open PowerShell and run:

```powershell
Test-Path 'C:\Program Files\ANSYS Inc\Shared Files\Licensing\winx64\lmgrd.exe'
```

Expected result:

- `True`

If result is `False`, installer did not complete correctly. Use Step 6 (manual fallback).

### 2.4 Start and verify the local FlexNet server

If service mode is installed, it may start automatically. If not, you can start it manually:

```powershell
cd 'C:\Users\Ian Poon\Desktop\LicenseServer\Shared Files\licensing\winx64\update'
Start-Process -FilePath .\lmgrd.exe -ArgumentList '-c','.\license.lic','-l','.\server.log' -NoNewWindow
```

Verify local STK feature availability:

```powershell
& 'C:\Program Files\AGI\STK_ODTK 13\licensingclient\winx64\lmutil.exe' lmstat -c 1055@localhost -f stk_mission_air
```

Expected output contains:

- `license server UP`
- `ansyslmd: UP`
- `Users of stk_mission_air`

---

## Step 3: Install STK

1. Extract the STK ZIP.
2. Run installer:
   - `...\STK_Installer\install.exe`
3. Install STK components.
4. Launch app selector and choose:
   - `STK` (not ODTK unless you have ODTK entitlement)

Important:

- If you see "A current ODTK license could not be found", that does not mean STK is broken; it means ODTK entitlement is missing.

---

## Step 4: Verify Entitlement Type

Your license file should include STK features such as:

- `stk_mission_air`
- `stk_mission_space`
- `stk_mission_level1/2/3`
- `stk_geodata`
- `stk_geoserver`

If STK opens but complains about missing license, the most common reason is:

- The remote server is reachable but does not serve `stk_*` features for your account.

---

## Step 5: If Remote Server Does Not Include STK Features

If remote server does not provide STK features, host your own local server.

1. Open Ansys Installation Launcher (`setup.exe` from `AnsysLicenseManager` package).
2. Select **Install Ansys License Manager** (bottom option).
3. Complete installation with admin permissions.
4. Use your generated `.lic` file when prompted.

If GUI installation is blocked or incomplete, you can still run locally by extracting licserv binaries (advanced/manual path shown in Step 6).

---

## Step 6: Manual FlexNet Server Activation (Advanced but Reliable)

Use this if the local service was not installed correctly.

### 5.1 Extract license server binaries

From PowerShell:

```powershell
New-Item -ItemType Directory -Path 'C:\Users\Ian Poon\Desktop\LicenseServer' -Force | Out-Null

tar -xf 'C:\Users\Ian Poon\Desktop\AnsysLicenseManager\licserv\WINX64.7z' \
  -C 'C:\Users\Ian Poon\Desktop\LicenseServer'
```

### 5.2 Prepare working folder and license file

```powershell
cd 'C:\Users\Ian Poon\Desktop\LicenseServer\Shared Files\licensing\winx64\update'
Copy-Item 'C:\Users\Ian Poon\Desktop\Ansys_license_1197757_70a8d321e17a.lic' .\license.lic -Force
```

### 5.3 Start FlexNet server (lmgrd)

```powershell
Start-Process -FilePath .\lmgrd.exe -ArgumentList '-c','.\license.lic','-l','.\server.log' -NoNewWindow
```

### 5.4 Verify STK feature is served

```powershell
& 'C:\Program Files\AGI\STK_ODTK 13\licensingclient\winx64\lmutil.exe' \
  lmstat -c 1055@localhost -f stk_mission_air
```

Expected output includes:

- `license server UP (MASTER)`
- `ansyslmd: UP`
- `Users of stk_mission_air: (Total of ... licenses issued ...)`

---

## Step 7: Point STK to the Correct Server

Edit STK licensing config file:

- `C:\Program Files\AGI\STK_ODTK 13\Shared Files\Licensing\ansyslmd.ini`

Recommended value for local hosting:

```ini
SERVER=1055@localhost
```

If you must use remote institutional server only:

```ini
SERVER=1055@ansysteach.cc.ic.ac.uk
```

Use local server when remote server does not provide `stk_*` features.

---

## Step 8: Set Environment Variables (Optional but Helpful)

```powershell
setx ANSYSLMD_LICENSE_FILE "1055@localhost"
setx LM_LICENSE_FILE "1055@localhost"
```

Restart terminal/session after `setx` so GUI apps inherit updated values.

---

## Step 9: Launch STK

```powershell
Start-Process -FilePath 'C:\Program Files\AGI\STK_ODTK 13\bin\AgUiApplication.exe'
```

In app selector, choose:

- `STK`

---

## Daily Start Commands (Quick Start)

If local server is not running after reboot:

```powershell
cd 'C:\Users\Ian Poon\Desktop\LicenseServer\Shared Files\licensing\winx64\update'
Start-Process -FilePath .\lmgrd.exe -ArgumentList '-c','.\license.lic','-l','.\server.log' -NoNewWindow
```

Check status:

```powershell
& 'C:\Program Files\AGI\STK_ODTK 13\licensingclient\winx64\lmutil.exe' lmstat -c 1055@localhost -f stk_mission_air
```

---

## Troubleshooting

### New user checklist (quick)

1. `ansysteach.cc.ic.ac.uk` in Licensing Settings works (green check).
2. Local License Manager installed (or manual fallback completed).
3. `lmstat -c 1055@localhost -f stk_mission_air` shows STK features.
4. `ansyslmd.ini` points to `SERVER=1055@localhost`.
5. Launch `STK`, not `ODTK`.

### Error: "Cannot connect to license server" for `1055@ianpoonWindows`

Cause:

- No local `lmgrd` process on port 1055.

Fix:

- Start local server with Step 5.3 and verify with Step 5.4.

### Error: "A current STK license could not be found"

Cause:

- Server reachable but no `stk_*` features available.

Fix:

- Use local license file/server with STK entitlement.
- Or ask institutional admin to add `stk_*` features to remote server.

### ODTK popup appears

Cause:

- ODTK started without ODTK entitlement.

Fix:

- Launch `STK` app, not `ODTK`.

### Green check in Licensing Settings but STK still fails

Cause:

- Green check only confirms server connectivity, not feature availability.

Fix:

- Run `lmstat -f stk_mission_air` against that server to confirm feature exists.

---

## Recommended Final Configuration

For reliable STK use with your own entitlement:

- STK config (`ansyslmd.ini`): `SERVER=1055@localhost`
- Local daemon running from extracted LicenseServer folder
- Verify feature using `lmutil lmstat -f stk_mission_air`

This setup avoids dependency on remote server feature assignments.
