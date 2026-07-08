# Cinesis Good Fit Test

## Assumptions
- **Current Location**: Dallas
- **Home Base**: San Antonio 
- **Min Rate**: $2.00/mile (Effective Rate used for conservative filtering)
- **Equipment**: Hotshot / Gooseneck (Flatbed loads also considered compatible if they meet weight restrictions).
- **Weight Capacity**: 12,000 lbs. A standard non-CDL hotshot gooseneck setup (typically ~25,900 lbs GVWR minus truck and trailer weight) yields a legal payload capacity of around 10,000 - 12,000 lbs. 

## Rejected High-Paying Load
- **L08 (Dallas to McAllen, $1700)** is the highest-paying load on the board. It was deliberately rejected because its weight (12,600 lbs) exceeds the assumed safe payload capacity (12,000 lbs) of the driver's hotshot gooseneck setup. Load L03 (14,200 lbs) was also rejected for this reason. Consequently, only 2 loads perfectly meet all strict criteria (L02 and L05). 

## Execution
The solution has been split into two scripts to match the prompt's two parts:
- Run `python part_a.py` to see the structured extracted driver profile.
- Run `python part_b.py` to see the ranked eligible loads matched against that profile.
