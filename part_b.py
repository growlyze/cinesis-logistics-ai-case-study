import pandas as pd
from haversine import haversine, Unit
from part_a import run_part_a

def run_part_b():
    print("\n--- PART B: Top Eligible Loads ---")
    profile = run_part_a()  # Get profile from Part A
    df = pd.read_excel('data.xlsx', sheet_name='Loads')
    
    # Driver coordinates based on current location and home base
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
        
        # Filter by equipment type (allow Hotshot, Gooseneck, Flatbed)
        # Note: A Hotshot Gooseneck can generally take flatbed loads as well if weight is okay
        if trailer not in profile["Equipment type(s)"] and trailer != "Flatbed":
            continue
            
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
        
        # Filter by minimum rate
        if eff_rate < profile["Min rate/mile"]:
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
    
    # Output the top 3
    print("\n[Ranked Results]")
    top_3 = eligible_loads[:3]
    for idx, load in enumerate(top_3):
        print(f"{idx+1}. {load['Load ID']} ({load['Origin']} -> {load['Destination']}) | {load['Trailer']} | {load['Weight']} lbs | ${load['Price']} | Eff Rate: ${load['Effective Rate']:.2f}/mile")

if __name__ == "__main__":
    run_part_b()
