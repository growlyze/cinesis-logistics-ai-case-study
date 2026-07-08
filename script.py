import pandas as pd
from haversine import haversine, Unit
import json

def run_part_a():
    profile = {
        "Current Location": "Dallas",
        "Home Base": "San Antonio",
        "Min rate/mile": 2.00,
        "Equipment type(s)": ["Hotshot", "Gooseneck"],
        "Weight capacity": 12000
    }
    print("--- PART A: Driver Profile ---")
    print(json.dumps(profile, indent=2))
    return profile

def run_part_b(profile):
    print("\n--- PART B: Top Eligible Loads ---")
    df = pd.read_excel('data.xlsx', sheet_name='Loads')
    
    # Driver coordinates
    loc_dallas = (32.7767, -96.7970)
    loc_sa = (29.4241, -98.4936)
    
    eligible_loads = []
    
    for i, row in df.iterrows():
        # Handle missing price
        if pd.isna(row['Price ($)']) or row['Price ($)'] == 'MISSING':
            continue
            
        # Handle missing destination
        if pd.isna(row['Dest Lat']) or row['Dest Lat'] == 'MISSING':
            continue
            
        price = float(row['Price ($)'])
        weight = float(row['Weight'])
        trailer = str(row['Trailer'])
        
        # Filter by equipment type
        if trailer not in profile["Equipment type(s)"] and trailer != "Flatbed":
            # Assuming Flatbed is acceptable on a Gooseneck if weight permits
            pass
            
        # Filter by weight capacity
        if weight > profile["Weight capacity"]:
            continue
            
        # Coordinates
        origin = (float(row['Origin Lat']), float(row['Origin Lon']))
        dest = (float(row['Dest Lat']), float(row['Dest Lon']))
        
        # Haversine distances
        deadhead_orig = haversine(loc_dallas, origin, unit=Unit.MILES)
        loaded_miles = haversine(origin, dest, unit=Unit.MILES)
        deadhead_home = haversine(dest, loc_sa, unit=Unit.MILES)
        
        total_miles = deadhead_orig + loaded_miles + deadhead_home
        eff_rate = price / total_miles
        
        # Filter by min rate
        if eff_rate < profile["Min rate/mile"]:
            continue
            
        # Must match Trailer Type
        if trailer not in profile["Equipment type(s)"] and trailer != 'Flatbed':
            continue
            
        eligible_loads.append({
            'Load ID': row['Load ID'],
            'Origin': row['Origin'],
            'Destination': row['Destination'],
            'Trailer': trailer,
            'Weight': weight,
            'Price': price,
            'Effective Rate': eff_rate
        })
        
    # Rank by effective rate descending
    eligible_loads.sort(key=lambda x: x['Effective Rate'], reverse=True)
    
    # Top 3
    top_3 = eligible_loads[:3]
    for idx, load in enumerate(top_3):
        print(f"{idx+1}. {load['Load ID']} ({load['Origin']} -> {load['Destination']}) | {load['Trailer']} | {load['Weight']} lbs | ${load['Price']} | Eff Rate: ${load['Effective Rate']:.2f}/mile")

if __name__ == "__main__":
    prof = run_part_a()
    run_part_b(prof)
