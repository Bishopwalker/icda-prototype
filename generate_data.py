"""Generate realistic mock customer data for ICDA prototype"""
import json
import random
from datetime import datetime, timedelta

# Realistic data pools
FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Christopher", "Karen", "Charles", "Lisa", "Daniel", "Nancy",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
    "Kenneth", "Dorothy", "Kevin", "Carol", "Brian", "Amanda", "George", "Melissa",
    "Timothy", "Deborah", "Ronald", "Stephanie", "Edward", "Rebecca", "Jason", "Sharon",
    "Jeffrey", "Laura", "Ryan", "Cynthia", "Jacob", "Kathleen", "Gary", "Amy",
    "Nicholas", "Angela", "Eric", "Shirley", "Jonathan", "Anna", "Stephen", "Brenda"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker",
    "Cruz", "Edwards", "Collins", "Reyes", "Stewart", "Morris", "Morales", "Murphy"
]

# State data with cities and zip ranges
STATES = {
    "NV": {
        "cities": [
            ("Las Vegas", "891"), ("Henderson", "890"), ("Reno", "895"),
            ("North Las Vegas", "890"), ("Sparks", "894"), ("Carson City", "897")
        ],
        "weight": 15  # Higher weight = more customers
    },
    "CA": {
        "cities": [
            ("Los Angeles", "900"), ("San Francisco", "941"), ("San Diego", "921"),
            ("Sacramento", "958"), ("San Jose", "951"), ("Fresno", "937"),
            ("Oakland", "946"), ("Long Beach", "908"), ("Bakersfield", "933")
        ],
        "weight": 20
    },
    "AZ": {
        "cities": [
            ("Phoenix", "850"), ("Tucson", "857"), ("Mesa", "852"),
            ("Scottsdale", "852"), ("Chandler", "852"), ("Tempe", "852")
        ],
        "weight": 12
    },
    "TX": {
        "cities": [
            ("Houston", "770"), ("Dallas", "752"), ("Austin", "787"),
            ("San Antonio", "782"), ("Fort Worth", "761"), ("El Paso", "799")
        ],
        "weight": 18
    },
    "FL": {
        "cities": [
            ("Miami", "331"), ("Orlando", "328"), ("Tampa", "336"),
            ("Jacksonville", "322"), ("Fort Lauderdale", "333"), ("West Palm Beach", "334")
        ],
        "weight": 14
    },
    "NY": {
        "cities": [
            ("New York", "100"), ("Buffalo", "142"), ("Rochester", "146"),
            ("Albany", "122"), ("Syracuse", "132"), ("Yonkers", "107")
        ],
        "weight": 10
    },
    "WA": {
        "cities": [
            ("Seattle", "981"), ("Spokane", "992"), ("Tacoma", "984"),
            ("Vancouver", "986"), ("Bellevue", "980"), ("Everett", "982")
        ],
        "weight": 8
    },
    "CO": {
        "cities": [
            ("Denver", "802"), ("Colorado Springs", "809"), ("Aurora", "800"),
            ("Fort Collins", "805"), ("Boulder", "803"), ("Lakewood", "802")
        ],
        "weight": 8
    },
    "VA": {
        "cities": [
            ("Virginia Beach", "234"), ("Norfolk", "235"), ("Richmond", "232"),
            ("Arlington", "222"), ("Alexandria", "223"), ("Chesapeake", "233")
        ],
        "weight": 5
    }
}

STREET_TYPES = ["St", "Ave", "Blvd", "Dr", "Ln", "Way", "Ct", "Pl", "Rd", "Cir"]
STREET_NAMES = [
    "Main", "Oak", "Cedar", "Maple", "Pine", "Elm", "Washington", "Lake", "Hill",
    "Park", "Spring", "Valley", "River", "Forest", "Sunset", "Highland", "Meadow",
    "Church", "Mill", "School", "Union", "Market", "Water", "Center", "Bridge"
]

def generate_address():
    """Generate a random street address"""
    num = random.randint(100, 9999)
    street = random.choice(STREET_NAMES)
    st_type = random.choice(STREET_TYPES)
    
    # Sometimes add apartment
    if random.random() < 0.3:
        apt = f" Apt {random.randint(1, 999)}"
    else:
        apt = ""
    
    return f"{num} {street} {st_type}{apt}"

def generate_zip(prefix):
    """Generate zip code from prefix"""
    suffix = str(random.randint(0, 99)).zfill(2)
    return f"{prefix}{suffix}"

def weighted_state_choice():
    """Choose state weighted by population distribution"""
    states = list(STATES.keys())
    weights = [STATES[s]["weight"] for s in states]
    return random.choices(states, weights=weights)[0]

def generate_move_history(move_count, last_move_date):
    """Generate move history entries"""
    history = []
    current_date = last_move_date
    
    for i in range(move_count):
        state = weighted_state_choice()
        city, zip_prefix = random.choice(STATES[state]["cities"])
        
        entry = {
            "from_address": generate_address() if i > 0 else None,
            "to_address": generate_address(),
            "city": city,
            "state": state,
            "zip": generate_zip(zip_prefix),
            "move_date": current_date.strftime("%Y-%m-%d")
        }
        history.append(entry)
        
        # Go back 6-24 months for each previous move
        current_date = current_date - timedelta(days=random.randint(180, 730))
    
    return history

def generate_customer(crid_num):
    """Generate a single customer record"""
    # Basic info
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    
    # Current location
    state = weighted_state_choice()
    city, zip_prefix = random.choice(STATES[state]["cities"])
    
    # Move count - weighted toward lower numbers (more realistic)
    move_weights = [30, 25, 20, 12, 7, 4, 2]  # 0-6 moves
    move_count = random.choices(range(len(move_weights)), weights=move_weights)[0]
    
    # Last move date - within past 3 years
    days_ago = random.randint(30, 1095)
    last_move = datetime.now() - timedelta(days=days_ago)
    
    # Customer type distribution
    cust_types = ["RESIDENTIAL", "BUSINESS", "PO_BOX"]
    cust_type = random.choices(cust_types, weights=[80, 15, 5])[0]
    
    # Status
    statuses = ["ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE", "INACTIVE", "PENDING"]
    status = random.choice(statuses)
    
    customer = {
        "crid": f"CRID-{str(crid_num).zfill(6)}",
        "name": f"{first} {last}",
        "first_name": first,
        "last_name": last,
        "address": generate_address(),
        "city": city,
        "state": state,
        "zip": generate_zip(zip_prefix),
        "customer_type": cust_type,
        "status": status,
        "move_count": move_count,
        "last_move": last_move.strftime("%Y-%m-%d") if move_count > 0 else None,
        "created_date": (datetime.now() - timedelta(days=random.randint(365, 2555))).strftime("%Y-%m-%d"),
        "move_history": generate_move_history(move_count, last_move) if move_count > 0 else []
    }
    
    return customer

def generate_dataset(count=2000):
    """Generate full dataset"""
    print(f"Generating {count} customer records...")
    customers = []
    
    for i in range(1, count + 1):
        customers.append(generate_customer(i))
        if i % 500 == 0:
            print(f"  Generated {i}/{count}...")
    
    return customers

def print_stats(customers):
    """Print dataset statistics"""
    print("\n" + "=" * 60)
    print("DATASET STATISTICS")
    print("=" * 60)
    
    # By state
    state_counts = {}
    for c in customers:
        state_counts[c["state"]] = state_counts.get(c["state"], 0) + 1
    
    print("\nCustomers by State:")
    for state, count in sorted(state_counts.items(), key=lambda x: -x[1]):
        print(f"  {state}: {count}")
    
    # Move count distribution
    move_counts = {}
    for c in customers:
        mc = c["move_count"]
        move_counts[mc] = move_counts.get(mc, 0) + 1
    
    print("\nMove Count Distribution:")
    for mc, count in sorted(move_counts.items()):
        print(f"  {mc} moves: {count} customers")
    
    # High movers (2+)
    high_movers = [c for c in customers if c["move_count"] >= 2]
    print(f"\nHigh Movers (2+ moves): {len(high_movers)}")
    
    # Nevada customers who moved twice (the demo query)
    nv_twice = [c for c in customers if c["state"] == "NV" and c["move_count"] >= 2]
    print(f"Nevada customers with 2+ moves: {len(nv_twice)}")

def main():
    # Generate
    customers = generate_dataset(2000)
    
    # Save to JSON
    output_file = "customer_data.json"
    with open(output_file, "w") as f:
        json.dump(customers, f, indent=2)
    
    print(f"\n✓ Saved to {output_file}")
    print(f"  File size: {len(json.dumps(customers)) / 1024:.1f} KB")
    
    # Print stats
    print_stats(customers)
    
    # Sample records
    print("\n" + "=" * 60)
    print("SAMPLE RECORDS")
    print("=" * 60)
    for c in customers[:3]:
        print(f"\n{c['crid']}: {c['name']}")
        print(f"  {c['address']}, {c['city']}, {c['state']} {c['zip']}")
        print(f"  Type: {c['customer_type']} | Status: {c['status']}")
        print(f"  Moves: {c['move_count']} | Last: {c['last_move']}")

if __name__ == "__main__":
    main()
