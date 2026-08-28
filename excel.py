import pandas as pd

input_path = "Students_Details_Final.csv.xls"
output_path = "Filtered_Students_Details.xlsx"

# 1. Load the data (handles CSVs saved with .xls extensions or standard Excel files)
try:
    df = pd.read_csv(input_path)
except Exception:
    df = pd.read_excel(input_path)

# 2. Normalize column headers (strip whitespace and lower case for easy matching)
df.columns = [col.strip().lower() for col in df.columns]

# 3. Identify and map relevant columns
# Update these if your file uses slightly different header names
name_col = next((c for c in df.columns if "name" in c), None)
dept_col = next((c for c in df.columns if any(k in c for k in ["dept", "department"])), None)
phone_col = next((c for c in df.columns if any(k in c for k in ["ph", "phone", "mobile", "contact"])), None)

# 4. Filter and rename
filtered_df = df[[name_col, dept_col, phone_col]].copy()
filtered_df.columns = ["Name", "Department", "Phone Number"]

# 5. Export to a clean Excel workbook
filtered_df.to_excel(output_path, index=False)
print(f"Extracted {len(filtered_df)} records into '{output_path}'.")
