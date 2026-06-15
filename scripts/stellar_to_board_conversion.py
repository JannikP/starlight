# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pandas",
# ]
# ///

"""
Convert stellar coordinates from stars_raw.csv to Cartesian coordinates
on a printed circuit board layout, then write results to stars_board.csv.

Coordinate system:
  - Origin (0, 0, 0) = Sol
  - x/y plane = equatorial plane
  - z = out of plane (shifted so minimum z is 1 cm above the x/y plane)

Spherical -> Cartesian:
  x = r * cos(dec) * cos(ra)
  y = r * cos(dec) * sin(ra)
  z = r * sin(dec)
"""

import math
import re

import pandas as pd

# --- Configuration -----------------------------------------------------------

MILLIMETERS_PER_LIGHTYEAR = 100.0 / 12.0  # mm / ly; Scale of the PCB.
MAX_EQUATORIAL_RADIUS     = 100.0  # mm; Filters entries by sqrt(x²+y²) from Sol.
MAX_HEIGHT                = 113.5  # mm; Filters entries by vertical distance from Sol.

INPUT_FILE  = "stars_raw.csv"
OUTPUT_FILE = "stars_board.csv"

# --- Coordinate parsers ------------------------------------------------------

def parse_ra_degrees(ra_str: str) -> float:
    """
    Parse a Right Ascension string (first value if ' / '-separated).
    Accepts formats like:
      '14h 29m 43.0s'
      '14h29m43.0s'
      'N/A'
    Returns decimal degrees
    """
    if not isinstance(ra_str, str):
        if math.isnan(ra_str):
            print("Found nan")
            return 0.0
        else:
            raise ValueError(f"Right Ascension must be a string, but is {type(ra_str)}.")

    # Take only the first entry for multi-star systems
    ra_str = ra_str.split(" / ")[0].strip()

    if ra_str.upper() in ("N/A", "", "—"):
        return 0.0

    # Match  14h 29m 43.0s  (spaces optional)
    m = re.match(
        r"(\d+)\s*h\s*(\d+)\s*m\s*([\d.]+)\s*s",
        ra_str,
        re.IGNORECASE,
    )
    if m:
        h, minutes, seconds = float(m.group(1)), float(m.group(2)), float(m.group(3))
        # 1 hour of RA = 15 degrees
        return (h + minutes / 60.0 + seconds / 3600.0) * 15.0

    raise ValueError("Right Ascension did not match RegEx.")

def parse_dec_degrees(dec_str: str) -> float:
    """
    Parse a Declination string (first value if ' / '-separated).
    Accepts formats like:
      '−62° 40′ 46″'
      '+04° 41′ 36″'
      'N/A'
    Returns decimal degrees
    """
    if not isinstance(dec_str, str):
        if math.isnan(dec_str):
            print("Found nan")
            return 0.0
        else:
            raise ValueError(f"Declination must be a string, but is {type(dec_str)}.")

    # Take only the first entry for multi-star systems
    dec_str = dec_str.split(" / ")[0].strip()

    if dec_str.upper() in ("N/A", "", "—"):
        return 0.0

    # Normalize minus signs (Unicode '−' -> ASCII '-')
    dec_str = dec_str.replace("\u2212", "-").replace("\u2013", "-")

    # Match  ±DD° MM′ SS″  (seconds optional)
    m = re.match(
        r"([+\-]?\d+)\s*[°d]\s*(\d+)\s*[′']\s*([\d.]+)\s*[″\"]?",
        dec_str,
    )
    if m:
        deg  = float(m.group(1))
        mins = float(m.group(2))
        secs = float(m.group(3))
        sign = -1.0 if deg < 0 else 1.0
        return deg + sign * (mins / 60.0 + secs / 3600.0)

    # Fallback: degrees only
    m2 = re.match(r"([+\-]?\d+\.?\d*)\s*°?", dec_str)
    if m2:
        return float(m2.group(1))

    raise ValueError("Declination did not match RegEx.")

# --- Cartesian conversion ----------------------------------------------------

def to_cartesian(
    distance_ly: float,
    ra_deg: float,
    dec_deg: float,
    scale: float,
) -> tuple[float, float, float]:
    """
    Convert spherical astronomical coordinates to Cartesian (mm).

    Parameters
    ----------
    distance_ly : distance in light-years
    ra_deg      : right ascension in decimal degrees
    dec_deg     : declination in decimal degrees
    scale       : mm per light-year

    Returns
    -------
    (x, y, z) in millimeters
    """
    # Scale and unit conversion
    r   = distance_ly * scale
    ra  = math.radians(ra_deg)
    dec = math.radians(dec_deg)

    # Polar to Cartesian
    x = r * math.cos(dec) * math.cos(ra)
    y = r * math.cos(dec) * math.sin(ra)
    z = r * math.sin(dec)

    # Round to 0.01 mm
    x, y, z = [round(v * 100.0) / 100.0 for v in [x, y, z]]
    return x, y, z

# --- Main --------------------------------------------------------------------

def main() -> None:
    # 1. Load raw data
    df = pd.read_csv(INPUT_FILE)

    # 2. Parse coordinates
    df["RA_deg"]  = df["Right_Ascension"].apply(parse_ra_degrees)
    df["Dec_deg"] = df["Declination"].apply(parse_dec_degrees)

    # 3. Convert to Cartesian; rows with unparsable coords get NaN
    results = []
    for _, row in df.iterrows():
        try:
            dist = float(str(row["Distance_ly"]).split(" / ")[0])
        except (ValueError, TypeError):
            dist = None

        ra  = row["RA_deg"]
        dec = row["Dec_deg"]

        if dist is None or ra is None or dec is None:
            results.append((None, None, None))
        else:
            results.append(to_cartesian(dist, ra, dec, MILLIMETERS_PER_LIGHTYEAR))

    df[["x_mm", "y_mm", "z_mm"]] = pd.DataFrame(
        results, index=df.index, columns=["x_mm", "y_mm", "z_mm"]
    )

    # Special case: Sol lives exactly at the origin
    sol_mask = df["System"].str.contains("Solar System", na=False)
    df.loc[sol_mask, ["x_mm", "y_mm", "z_mm"]] = 0.0

    # 4. Filter by equatorial radius sqrt(x² + y²)
    df["equatorial_radius_mm"] = (df["x_mm"] ** 2 + df["y_mm"] ** 2) ** 0.5

    within_mask = df["equatorial_radius_mm"] <= MAX_EQUATORIAL_RADIUS
    vertical_mask = df["z_mm"].abs() <= MAX_HEIGHT
    mask = within_mask & vertical_mask
    df_board = df[mask].copy()

    # 5. Shift z so the minimum z-value sits 1 cm above the x/y plane
    valid_z = df_board["z_mm"].dropna()
    if not valid_z.empty:
        z_min = valid_z.min()
        df_board["z_mm"] = df_board["z_mm"] + (10.0 - z_min)
    
    # 6. Write output
    df_board.to_csv(OUTPUT_FILE, index=False)

    # 7. Report
    total   = len(df)
    within  = len(df_board)
    outside = total - within
    z_max = df_board["z_mm"].max()

    print(f"Total systems loaded      : {total}")
    print(f"Within MAX_EQUATORIAL_RADIUS ({MAX_EQUATORIAL_RADIUS} mm): {within}")
    print(f"Outside / filtered out    : {outside}")
    print(f"Max height                : {z_max:.01f} mm")
    print(f"Results written to        : {OUTPUT_FILE}")

if __name__ == "__main__":
    main()