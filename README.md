# Cinesis Good Fit Test

## Assumptions
- **Current Location**: Dallas
- **Home Base**: San Antonio 
- **Min Rate**: $2.00/mile (Effective rate logic used)
- **Equipment**: Hotshot / Gooseneck (Flatbed loads considered compatible if weight permits).
- **Weight Capacity**: 12,000 lbs. A standard non-CDL hotshot gooseneck setup yields a safe payload capacity of around 10,000 - 12,000 lbs.

## Rejected High-Paying Load
- **L08 (Dallas to McAllen, $1700)** is the highest-paying load. It was deliberately rejected because its weight (12,600 lbs) exceeds the assumed payload capacity (12,000 lbs) of the driver's setup. Load L03 (14,200 lbs) was also rejected for this reason. Consequently, only 2 loads meet all strict criteria (L02 and L05).

## Missing Data Approach
- Loads missing prices (L06) or destination coordinates (L07) were gracefully skipped during parsing. Calculating their effective rate/mile is mathematically impossible, so they cannot be ranked.

## Execution
- Run `python part_a.py` to view the structured driver profile.
- Run `python part_b.py` to view the ranked eligible loads.
