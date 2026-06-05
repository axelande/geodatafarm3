## How to create a guide file

A guide file (also known as a prescription map or variable-rate application map) lets you turn your collected field data into a shapefile that your machinery can use for site-specific management. GeoDataFarm builds a grid over your field and calculates a value for each cell based on an equation you define.

### Prerequisites

Before you start, make sure you have:

- Created a farm and connected to it.
- Added at least one field.
- Imported at least one data set (e.g. harvest, soil, fertiliser) for that field.

---

### Open the Create Guide File dialog

In the GeoDataFarm dock widget, scroll down to the **Guide file** section under the **Plan ahead** tab. You will see the label *"Based on data sets, do you want to create a guide file?"* and a button **Create guide file**. Click it.

This opens the **Create guide file** dialog, which is divided into three steps.

---

### Step 1 — Select data source and field

At the top of the dialog you will find two drop-downs:

| Setting | Description |
|---------|-------------|
| **Data source** | The category of data to use: `plant`, `ferti`, `spray`, `harvest`, `soil`, or `other`. |
| **Field** | The field you want to create a guide file for. |

1. Select a **Data source** (e.g. `harvest`).
2. Select a **Field** from the drop-down.

The available-attributes table (Step 2) will update automatically to show only tables and columns that match your selection.

![Step 1 – Dialog after selecting data source and field](images/create_guide_file_01_step1.png)
<!-- Screenshot: the full dialog after selecting a data source and field, showing the available attributes table populated -->

---

### Step 2 — Select attributes and build an equation

The middle section has three panels side by side:

#### Available attributes (left panel)

This table lists every numeric column from the data tables that match your data source and field. Each row shows the table name (e.g. `harvest.harvest_2024`) and a drop-down of its numeric columns.

**Click a column in the drop-down** to add it to the *Selected attributes* list.

#### Selected attributes (middle panel)

Every attribute you click is added here with a reference number: `[0]`, `[1]`, `[2]`, etc. You use these references in the equation.

To remove an attribute, select its row and click **Remove selected**.

#### Equation (right panel)

Write a mathematical expression using the reference numbers. For example:

| Equation | Meaning |
|----------|---------|
| `[0]` | Use the raw value of the first attribute |
| `100 + [0] * 2` | Scale the first attribute and add a base value |
| `([0] + [1]) / 2` | Average two attributes |
| `[0] * 0.8 + [1] * 0.2` | Weighted combination |

The equation supports `+`, `-`, `*`, `/`, `//` (floor division), `%` (modulo), `**` (power) and parentheses.

A default example equation `100 + [0] * 2` is pre-filled as a starting point.

#### Calculate min/max

After writing your equation, click **Calculate min/max**. GeoDataFarm queries the database and evaluates the equation for the maximum and minimum values of your selected attributes within the chosen field. The results are displayed below the button:

```
Max value: 312.5
Min value: 87.2
```

This gives you a quick preview of the output range so you can adjust the equation before creating the file.

---

### Step 3 — Configure output and create the file

The bottom section contains the output settings:

| Setting | Default | Description |
|---------|---------|-------------|
| **Data type** | `Integer (1)` | Choose `Integer (1)` or `Float (1.234)` depending on what your machine expects. |
| **Cell size (m)** | `25` | The grid resolution in metres. A smaller value gives a finer grid but a larger file. |
| **EPSG** | `4326` | The coordinate reference system code. Leave as `4326` (WGS 84) unless your machine requires a different CRS. For Swedish fields, `3006` (SWEREF99 TM) is common. |
| **Rotation (deg)** | `0` | Rotate the grid by this many degrees. Useful if your tramlines run at an angle. |
| **Attribute name** | `Setting_distance` | The name of the attribute column in the output shapefile (max 10 characters). |
| **File name** | `guide_file` | The output file name (without extension). |

#### Select output folder

Click **Select folder...** to choose where the shapefile will be saved. The selected path is shown next to the button.

#### Create the file

Once everything is configured, click the green **Create Guide File** button.

![Step 3 – Dialog ready to create the file](images/create_guide_file_02_step3.png)
<!-- Screenshot: the full dialog with attributes selected, equation filled in, min/max calculated, output settings configured, and the green "Create Guide File" button enabled -->

GeoDataFarm will:

1. Generate a grid over your field with the specified cell size.
2. Optionally rotate the grid.
3. For each grid cell, calculate the equation value by averaging the selected attributes from data points that fall inside the cell.
4. Write a shapefile (`.shp`, `.shx`, `.dbf`, `.prj`) to your chosen folder.
5. Add the result as a styled layer to your QGIS map canvas.

---

### Tips

- **Check the min/max values** before creating the file. If the range looks wrong, adjust the equation or verify that the correct data set is selected.
- **Cell size** has a big impact: 10 m gives very detailed grids (good for variable-rate seeding), while 50 m may be enough for fertiliser spreading.
- **EPSG matters** — if your terminal or auto-steering system expects a projected CRS (metres), set the EPSG accordingly. Using `4326` (degrees) may cause issues on some equipment.
- **Rotation** is applied around the centroid of the grid. A few degrees can make a big difference when aligning with tramlines.
- You can combine multiple data sources by selecting attributes from different tables (e.g. one from `harvest` and one from `soil`) and combining them in the equation.
- Click the **Help** button in the top-right corner of the dialog for a quick summary of the workflow.

---

### Example workflow

1. Open the Create guide file dialog.
2. Set **Data source** to `harvest` and select your field.
3. Click the `yield` column from `harvest.harvest_2024` → it becomes `[0]`.
4. Click the `clay_content` column from `soil.soil_samples` → it becomes `[1]`.
5. Enter the equation: `80 + [0] * 0.5 - [1] * 0.3`
6. Click **Calculate min/max** to verify the range.
7. Set **Cell size** to `20`, **EPSG** to `3006`, **Data type** to `Integer (1)`.
8. Set **File name** to `fert_guide_2026`.
9. Select an output folder and click **Create Guide File**.
10. The guide file appears on the QGIS canvas — ready to load onto your terminal.
