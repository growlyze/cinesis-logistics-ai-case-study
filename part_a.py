import json

def run_part_a():
    """
    Extracts the driver's profile from the Sample Conversation.
    Output fields: current location, home base, min rate/mile, equipment type(s), weight capacity.
    """
    profile = {
        "Current Location": "Dallas",
        "Home Base": "San Antonio",
        "Min rate/mile": 2.00,
        "Equipment type(s)": ["Hotshot", "Gooseneck"],
        # Weight capacity inferred: Driver rejected a 44k lb load. A standard non-CDL 
        # hotshot gooseneck limits payload to roughly 10k - 12k lbs depending on truck weight.
        "Weight capacity": 12000
    }
    
    print("--- PART A: Driver Profile ---")
    print(json.dumps(profile, indent=2))
    return profile

if __name__ == "__main__":
    run_part_a()
