META DATA FILES
===============

This folder contains XML files that store metadata for ISOXML task generation.
These files may contain personal data (farm names, worker names, etc.) and
are excluded from git.

SETUP FOR NEW DEVELOPERS
------------------------
Copy each *.xml.template file to create the corresponding *.xml file:

  FRMs.xml.template -> FRMs.xml  (Farms)
  CTRs.xml.template -> CTRs.xml  (Customers/Clients)
  WRKs.xml.template -> WRKs.xml  (Workers)
  DVCs.xml.template -> DVCs.xml  (Devices)
  PDTs.xml.template -> PDTs.xml  (Products)
  PGPs.xml.template -> PGPs.xml  (Product Groups)
  VPNs.xml.template -> VPNs.xml  (Value Presentations)
  CPCs.xml.template -> CPCs.xml  (Cultural Practices)
  OTQs.xml.template -> OTQs.xml  (Operation Techniques)
  CTPs.xml.template -> CTPs.xml  (Crop Types)
  CCGs.xml.template -> CCGs.xml  (Coded Comment Groups)

On Windows (PowerShell):
  Get-ChildItem *.template | ForEach-Object { Copy-Item $_ ($_.Name -replace '\.template$','') }

On Linux/Mac:
  for f in *.template; do cp "$f" "${f%.template}"; done

The template files contain minimal test data. You can then add your own
metadata entries through the application.

GIT BEHAVIOR
------------
- *.xml files are ignored (your personal data stays local)
- *.xml.template files are tracked (shared with other developers)

If you update the template structure, edit the *.xml.template files directly.
