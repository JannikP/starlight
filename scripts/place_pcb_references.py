# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pandas",
# ]
# ///

"""
Moves reference circles on the `starlight.kicad_pcb` file to the PCB locations
from the `stars_board.csv` file.
"""

import pathlib
import re

import pandas as pd

# --- Configuration -----------------------------------------------------------

INPUT_FILE = "stars_board.csv"
PCB_FILE = "starlight.kicad_pcb"
OFFSET_X = 145.5
OFFSET_Y = 200.0

# --- Main --------------------------------------------------------------------

def main() -> None:
    # Read star locations from csv file
    df = pd.read_csv(INPUT_FILE)

    # Define the regex pattern to match the reference circles in the PCB file
    pattern = re.compile(r"\s+\(gr_circle\s+\(center (?P<cx>\d+(\.\d+)?) (?P<cy>\d+(\.\d+)?)\)\s+\(end (?P<ex>\d+(\.\d+)?) (?P<ey>\d+(\.\d+)?)\)\s+\(stroke\s+\(width 0.1\)\s+\(type dash\)\s+\)\s+\(fill no\)\s+\(layer \"Cmts\.User\"\)\s+\(uuid \"(?P<uuid>[a-z0-9\-]+)\"\)\s+\)")
    
    # Collect what to replace
    path = pathlib.Path(PCB_FILE)
    content = path.read_text(encoding="UTF-8")
    replacements = {}
    for match, (_, row) in zip(pattern.finditer(content), df.iterrows()):
        uuid = match.group("uuid")
        name = row["System"]
        print(f"Using {uuid} for {name}.")

        cx = row["x_mm"] + OFFSET_X
        cy = row["y_mm"] + OFFSET_Y
        ex = cx
        ey = cy + 1.2

        new_text = f"""    (gr_circle
		(center {cx:.2f} {cy:.2f})
		(end {ex:.2f} {ey:.2f})
		(stroke
			(width 0.1)
			(type dash)
		)
		(fill no)
		(layer "Cmts.User")
		(uuid "{uuid}")
	)
"""
        replacements[match.group(0)] = new_text
    
    # Perform all replacements
    for old, new in replacements.items():
        content = content.replace(old, new, 1)
    
    # Write back to file
    path.write_text(content, encoding="UTF-8")

if __name__ == "__main__":
    main()