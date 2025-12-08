"""Generate realistic mock customer data for ICDA prototype - 50K dataset with relationships"""
import json
import random
from datetime import datetime, timedelta
from typing import Optional

# Realistic data pools - expanded
FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Christopher", "Karen", "Charles", "Lisa", "Daniel", "Nancy",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
    "Kenneth", "Dorothy", "Kevin", "Carol", "Brian", "Amanda", "George", "Melissa",
    "Timothy", "Deborah", "Ronald", "Stephanie", "Edward", "Rebecca", "Jason", "Sharon",
    "Jeffrey", "Laura", "Ryan", "Cynthia", "Jacob", "Kathleen", "Gary", "Amy",
    "Nicholas", "Angela", "Eric", "Shirley", "Jonathan", "Anna", "Stephen", "Brenda",
    "Larry", "Pamela", "Justin", "Emma", "Scott", "Nicole", "Brandon", "Helen",
    "Benjamin", "Samantha", "Samuel", "Katherine", "Raymond", "Christine", "Gregory", "Debra",
    "Frank", "Rachel", "Alexander", "Carolyn", "Patrick", "Janet", "Jack", "Catherine",
    "Dennis", "Maria", "Jerry", "Heather", "Tyler", "Diane", "Aaron", "Ruth",
    "Jose", "Julie", "Adam", "Olivia", "Nathan", "Joyce", "Henry", "Virginia",
    "Douglas", "Victoria", "Zachary", "Kelly", "Peter", "Lauren", "Kyle", "Christina",
    "Noah", "Joan", "Ethan", "Evelyn", "Jeremy", "Judith", "Walter", "Megan",
    "Christian", "Andrea", "Keith", "Cheryl", "Roger", "Hannah", "Terry", "Jacqueline",
    "Austin", "Martha", "Sean", "Gloria", "Gerald", "Teresa", "Carl", "Ann",
    "Dylan", "Sara", "Harold", "Madison", "Jordan", "Frances", "Jesse", "Kathryn",
    "Bryan", "Janice", "Lawrence", "Jean", "Arthur", "Abigail", "Gabriel", "Alice"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker",
    "Cruz", "Edwards", "Collins", "Reyes", "Stewart", "Morris", "Morales", "Murphy",
    "Cook", "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper", "Peterson", "Bailey",
    "Reed", "Kelly", "Howard", "Ramos", "Kim", "Cox", "Ward", "Richardson", "Watson",
    "Brooks", "Chavez", "Wood", "James", "Bennett", "Gray", "Mendoza", "Ruiz", "Hughes",
    "Price", "Alvarez", "Castillo", "Sanders", "Patel", "Myers", "Long", "Ross", "Foster",
    "Jimenez", "Powell", "Jenkins", "Perry", "Russell", "Sullivan", "Bell", "Coleman",
    "Butler", "Henderson", "Barnes", "Gonzales", "Fisher", "Vasquez", "Simmons", "Stokes",
    "Stone", "Ferguson", "Murray", "Ford", "Hamilton", "Graham", "Wallace", "Woods",
    "Cole", "West", "Jordan", "Owens", "Reynolds", "Fisher", "Ellis", "Harrison"
]

# Business names for BUSINESS type customers
BUSINESS_PREFIXES = [
    "ABC", "First", "Golden", "Pacific", "Mountain", "Valley", "Metro", "National",
    "American", "United", "Central", "Western", "Eastern", "Northern", "Southern",
    "Premium", "Elite", "Prime", "Superior", "Quality", "Advanced", "Modern", "Classic"
]

BUSINESS_TYPES = [
    "Consulting", "Services", "Solutions", "Industries", "Enterprises", "Group",
    "Holdings", "Partners", "Associates", "Corporation", "Technologies", "Systems",
    "Management", "Development", "Properties", "Investments", "Logistics", "Trading"
]

# State data with cities and zip ranges
STATES = {
    "NV": {
        "cities": [
            ("Las Vegas", "891"), ("Henderson", "890"), ("Reno", "895"),
            ("North Las Vegas", "890"), ("Sparks", "894"), ("Carson City", "897"),
            ("Summerlin", "891"), ("Paradise", "891"), ("Spring Valley", "891")
        ],
        "weight": 15
    },
    "CA": {
        "cities": [
            ("Los Angeles", "900"), ("San Francisco", "941"), ("San Diego", "921"),
            ("Sacramento", "958"), ("San Jose", "951"), ("Fresno", "937"),
            ("Oakland", "946"), ("Long Beach", "908"), ("Bakersfield", "933"),
            ("Anaheim", "928"), ("Santa Ana", "927"), ("Riverside", "925"),
            ("Stockton", "952"), ("Irvine", "926"), ("Chula Vista", "919")
        ],
        "weight": 25
    },
    "AZ": {
        "cities": [
            ("Phoenix", "850"), ("Tucson", "857"), ("Mesa", "852"),
            ("Scottsdale", "852"), ("Chandler", "852"), ("Tempe", "852"),
            ("Gilbert", "852"), ("Glendale", "853"), ("Peoria", "853")
        ],
        "weight": 14
    },
    "TX": {
        "cities": [
            ("Houston", "770"), ("Dallas", "752"), ("Austin", "787"),
            ("San Antonio", "782"), ("Fort Worth", "761"), ("El Paso", "799"),
            ("Arlington", "760"), ("Plano", "750"), ("Corpus Christi", "784"),
            ("Lubbock", "794"), ("Irving", "750"), ("Laredo", "780")
        ],
        "weight": 22
    },
    "FL": {
        "cities": [
            ("Miami", "331"), ("Orlando", "328"), ("Tampa", "336"),
            ("Jacksonville", "322"), ("Fort Lauderdale", "333"), ("West Palm Beach", "334"),
            ("St. Petersburg", "337"), ("Hialeah", "330"), ("Tallahassee", "323"),
            ("Cape Coral", "339"), ("Pembroke Pines", "330"), ("Hollywood", "330")
        ],
        "weight": 18
    },
    "NY": {
        "cities": [
            ("New York", "100"), ("Buffalo", "142"), ("Rochester", "146"),
            ("Albany", "122"), ("Syracuse", "132"), ("Yonkers", "107"),
            ("White Plains", "106"), ("New Rochelle", "108"), ("Mount Vernon", "105")
        ],
        "weight": 12
    },
    "WA": {
        "cities": [
            ("Seattle", "981"), ("Spokane", "992"), ("Tacoma", "984"),
            ("Vancouver", "986"), ("Bellevue", "980"), ("Everett", "982"),
            ("Kent", "980"), ("Renton", "980"), ("Federal Way", "983")
        ],
        "weight": 10
    },
    "CO": {
        "cities": [
            ("Denver", "802"), ("Colorado Springs", "809"), ("Aurora", "800"),
            ("Fort Collins", "805"), ("Boulder", "803"), ("Lakewood", "802"),
            ("Thornton", "802"), ("Arvada", "800"), ("Westminster", "800")
        ],
        "weight": 10
    },
    "VA": {
        "cities": [
            ("Virginia Beach", "234"), ("Norfolk", "235"), ("Richmond", "232"),
            ("Arlington", "222"), ("Alexandria", "223"), ("Chesapeake", "233"),
            ("Newport News", "236"), ("Hampton", "236"), ("Roanoke", "240")
        ],
        "weight": 8
    },
    "GA": {
        "cities": [
            ("Atlanta", "303"), ("Augusta", "309"), ("Columbus", "319"),
            ("Savannah", "314"), ("Athens", "306"), ("Macon", "312")
        ],
        "weight": 10
    },
    "NC": {
        "cities": [
            ("Charlotte", "282"), ("Raleigh", "276"), ("Greensboro", "274"),
            ("Durham", "277"), ("Winston-Salem", "271"), ("Fayetteville", "283")
        ],
        "weight": 8
    },
    "IL": {
        "cities": [
            ("Chicago", "606"), ("Aurora", "605"), ("Naperville", "605"),
            ("Rockford", "611"), ("Joliet", "604"), ("Springfield", "627")
        ],
        "weight": 10
    },
    "PA": {
        "cities": [
            ("Philadelphia", "191"), ("Pittsburgh", "152"), ("Allentown", "181"),
            ("Reading", "196"), ("Erie", "165"), ("Scranton", "185")
        ],
        "weight": 8
    },
    "OH": {
        "cities": [
            ("Columbus", "432"), ("Cleveland", "441"), ("Cincinnati", "452"),
            ("Toledo", "436"), ("Akron", "443"), ("Dayton", "454")
        ],
        "weight": 8
    },
    "MI": {
        "cities": [
            ("Detroit", "482"), ("Grand Rapids", "495"), ("Warren", "480"),
            ("Ann Arbor", "481"), ("Lansing", "489"), ("Flint", "485")
        ],
        "weight": 6
    }
}

STREET_TYPES = ["St", "Ave", "Blvd", "Dr", "Ln", "Way", "Ct", "Pl", "Rd", "Cir", "Pkwy", "Ter"]
STREET_NAMES = [
    "Main", "Oak", "Cedar", "Maple", "Pine", "Elm", "Washington", "Lake", "Hill",
    "Park", "Spring", "Valley", "River", "Forest", "Sunset", "Highland", "Meadow",
    "Church", "Mill", "School", "Union", "Market", "Water", "Center", "Bridge",
    "Walnut", "Chestnut", "Willow", "Cherry", "Birch", "Dogwood", "Magnolia",
    "Hickory", "Cypress", "Spruce", "Poplar", "Aspen", "Redwood", "Sycamore",
    "Broadway", "Jackson", "Lincoln", "Jefferson", "Madison", "Monroe", "Adams",
    "Franklin", "Kennedy", "Roosevelt", "Wilson", "Harrison", "Cleveland", "Grant"
]

# Relationship types
RELATIONSHIP_TYPES = ["SPOUSE", "PARENT", "CHILD", "SIBLING", "PARTNER", "ROOMMATE"]

# Track generated data for relationships
generated_households = []  # List of (address, city, state, zip, members[])
generated_businesses = []  # List of (business_name, locations[])

def generate_address():
    """Generate a random street address"""
    num = random.randint(100, 9999)
    street = random.choice(STREET_NAMES)
    st_type = random.choice(STREET_TYPES)

    # Sometimes add apartment
    if random.random() < 0.25:
        apt = f" Apt {random.randint(1, 999)}"
    elif random.random() < 0.1:
        apt = f" Suite {random.randint(100, 999)}"
    elif random.random() < 0.05:
        apt = f" Unit {random.choice('ABCDEFGH')}"
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

def generate_business_name():
    """Generate a realistic business name"""
    if random.random() < 0.3:
        # Use a person's last name
        return f"{random.choice(LAST_NAMES)} {random.choice(BUSINESS_TYPES)}"
    else:
        return f"{random.choice(BUSINESS_PREFIXES)} {random.choice(BUSINESS_TYPES)}"

def generate_move_history(move_count, last_move_date, current_state=None):
    """Generate move history entries"""
    history = []
    current_date = last_move_date
    prev_address = None

    for i in range(move_count):
        # Sometimes stay in same state (more realistic)
        if current_state and random.random() < 0.4:
            state = current_state
        else:
            state = weighted_state_choice()

        city, zip_prefix = random.choice(STATES[state]["cities"])
        to_address = generate_address()

        entry = {
            "from_address": prev_address,
            "to_address": to_address,
            "city": city,
            "state": state,
            "zip": generate_zip(zip_prefix),
            "move_date": current_date.strftime("%Y-%m-%d")
        }
        history.append(entry)
        prev_address = to_address

        # Go back 6-24 months for each previous move
        current_date = current_date - timedelta(days=random.randint(180, 730))

    return history

def generate_customer(crid_num, household_info=None, business_info=None, relationship=None):
    """Generate a single customer record"""
    # Basic info
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)

    # If part of household, share last name sometimes
    if household_info and random.random() < 0.7:
        last = household_info.get("last_name", last)

    # Customer type distribution
    if business_info:
        cust_type = "BUSINESS"
    else:
        cust_types = ["RESIDENTIAL", "BUSINESS", "PO_BOX"]
        cust_type = random.choices(cust_types, weights=[82, 13, 5])[0]

    # Current location
    if household_info:
        state = household_info["state"]
        city = household_info["city"]
        zip_code = household_info["zip"]
        address = household_info["address"]
    elif business_info:
        loc = random.choice(business_info["locations"])
        state = loc["state"]
        city = loc["city"]
        zip_code = loc["zip"]
        address = loc["address"]
    else:
        state = weighted_state_choice()
        city, zip_prefix = random.choice(STATES[state]["cities"])
        zip_code = generate_zip(zip_prefix)
        address = generate_address()

    # Move count - weighted toward lower numbers (more realistic)
    move_weights = [25, 28, 22, 12, 7, 4, 2]  # 0-6 moves
    move_count = random.choices(range(len(move_weights)), weights=move_weights)[0]

    # Last move date - within past 3 years
    days_ago = random.randint(30, 1095)
    last_move = datetime.now() - timedelta(days=days_ago)

    # Status
    statuses = ["ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE", "INACTIVE", "PENDING"]
    status = random.choice(statuses)

    # Name for business customers
    if cust_type == "BUSINESS" and business_info:
        display_name = business_info["name"]
    else:
        display_name = f"{first} {last}"

    customer = {
        "crid": f"CRID-{str(crid_num).zfill(6)}",
        "name": display_name,
        "first_name": first,
        "last_name": last,
        "address": address,
        "city": city,
        "state": state,
        "zip": zip_code,
        "customer_type": cust_type,
        "status": status,
        "move_count": move_count,
        "last_move": last_move.strftime("%Y-%m-%d") if move_count > 0 else None,
        "created_date": (datetime.now() - timedelta(days=random.randint(365, 2555))).strftime("%Y-%m-%d"),
        "move_history": generate_move_history(move_count, last_move, state) if move_count > 0 else []
    }

    # Add relationship info if provided
    if relationship:
        customer["related_crid"] = relationship["related_crid"]
        customer["relationship_type"] = relationship["type"]

    if business_info:
        customer["business_name"] = business_info["name"]
        if len(business_info["locations"]) > 1:
            customer["branch_count"] = len(business_info["locations"])

    return customer

def generate_household():
    """Generate a household with shared address"""
    state = weighted_state_choice()
    city, zip_prefix = random.choice(STATES[state]["cities"])

    return {
        "address": generate_address(),
        "city": city,
        "state": state,
        "zip": generate_zip(zip_prefix),
        "last_name": random.choice(LAST_NAMES),
        "members": []
    }

def generate_business():
    """Generate a business with potentially multiple locations"""
    name = generate_business_name()
    num_locations = random.choices([1, 2, 3, 4], weights=[70, 20, 7, 3])[0]

    locations = []
    for _ in range(num_locations):
        state = weighted_state_choice()
        city, zip_prefix = random.choice(STATES[state]["cities"])
        locations.append({
            "address": generate_address(),
            "city": city,
            "state": state,
            "zip": generate_zip(zip_prefix)
        })

    return {
        "name": name,
        "locations": locations,
        "employees": []
    }

def generate_dataset(count=50000):
    """Generate full dataset with relationships"""
    print(f"Generating {count} customer records with relationships...")
    customers = []
    crid_num = 1

    # Pre-generate households (about 15% of customers will be in households)
    num_households = int(count * 0.08)  # 8% of records are household anchors
    print(f"  Creating {num_households} household groups...")
    households = [generate_household() for _ in range(num_households)]

    # Pre-generate businesses (about 5% of customers)
    num_businesses = int(count * 0.03)  # 3% are business anchors
    print(f"  Creating {num_businesses} business entities...")
    businesses = [generate_business() for _ in range(num_businesses)]

    # Generate household members (2-5 members each)
    print("  Generating household members...")
    for household in households:
        num_members = random.choices([2, 3, 4, 5], weights=[50, 30, 15, 5])[0]
        first_member_crid = crid_num

        for i in range(num_members):
            if i == 0:
                # First member - no relationship
                customer = generate_customer(crid_num, household_info=household)
            else:
                # Subsequent members - related to first
                rel_type = random.choice(["SPOUSE", "CHILD", "SIBLING", "ROOMMATE", "PARENT"])
                relationship = {
                    "related_crid": f"CRID-{str(first_member_crid).zfill(6)}",
                    "type": rel_type
                }
                customer = generate_customer(crid_num, household_info=household, relationship=relationship)

            customers.append(customer)
            household["members"].append(crid_num)
            crid_num += 1

    print(f"    Created {crid_num - 1} household members")

    # Generate business employees (1-10 per business)
    print("  Generating business records...")
    for business in businesses:
        num_employees = random.choices([1, 2, 3, 5, 8, 10], weights=[40, 25, 15, 10, 7, 3])[0]

        for i in range(num_employees):
            customer = generate_customer(crid_num, business_info=business)
            customers.append(customer)
            business["employees"].append(crid_num)
            crid_num += 1

    print(f"    Created {crid_num - 1 - len([c for c in customers if 'related_crid' not in c or 'business_name' not in c])} business records")

    # Generate remaining individual customers
    remaining = count - len(customers)
    print(f"  Generating {remaining} individual customers...")

    batch_size = 5000
    for batch_start in range(0, remaining, batch_size):
        batch_end = min(batch_start + batch_size, remaining)
        for i in range(batch_start, batch_end):
            customers.append(generate_customer(crid_num))
            crid_num += 1
        print(f"    Generated {min(batch_end, remaining)}/{remaining}...")

    # Shuffle to mix household/business/individual customers
    print("  Shuffling dataset...")
    random.shuffle(customers)

    # Re-assign CRIDs after shuffle to maintain order
    print("  Reassigning CRIDs...")
    crid_map = {}  # old_crid -> new_crid
    for i, customer in enumerate(customers):
        old_crid = customer["crid"]
        new_crid = f"CRID-{str(i + 1).zfill(6)}"
        crid_map[old_crid] = new_crid
        customer["crid"] = new_crid

    # Update relationship references
    for customer in customers:
        if "related_crid" in customer and customer["related_crid"] in crid_map:
            customer["related_crid"] = crid_map[customer["related_crid"]]

    return customers

def print_stats(customers):
    """Print dataset statistics"""
    print("\n" + "=" * 70)
    print("DATASET STATISTICS")
    print("=" * 70)

    print(f"\nTotal Customers: {len(customers):,}")

    # By state
    state_counts = {}
    for c in customers:
        state_counts[c["state"]] = state_counts.get(c["state"], 0) + 1

    print("\nCustomers by State:")
    for state, count in sorted(state_counts.items(), key=lambda x: -x[1])[:10]:
        pct = count / len(customers) * 100
        print(f"  {state}: {count:,} ({pct:.1f}%)")
    print(f"  ... and {len(state_counts) - 10} more states")

    # By customer type
    type_counts = {}
    for c in customers:
        type_counts[c["customer_type"]] = type_counts.get(c["customer_type"], 0) + 1

    print("\nCustomer Types:")
    for ctype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        pct = count / len(customers) * 100
        print(f"  {ctype}: {count:,} ({pct:.1f}%)")

    # By status
    status_counts = {}
    for c in customers:
        status_counts[c["status"]] = status_counts.get(c["status"], 0) + 1

    print("\nStatus Distribution:")
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        pct = count / len(customers) * 100
        print(f"  {status}: {count:,} ({pct:.1f}%)")

    # Move count distribution
    move_counts = {}
    for c in customers:
        mc = c["move_count"]
        move_counts[mc] = move_counts.get(mc, 0) + 1

    print("\nMove Count Distribution:")
    for mc, count in sorted(move_counts.items()):
        pct = count / len(customers) * 100
        print(f"  {mc} moves: {count:,} ({pct:.1f}%)")

    # Relationships
    with_relationships = [c for c in customers if "related_crid" in c]
    print(f"\nCustomers with Relationships: {len(with_relationships):,}")

    rel_types = {}
    for c in with_relationships:
        rt = c["relationship_type"]
        rel_types[rt] = rel_types.get(rt, 0) + 1

    print("Relationship Types:")
    for rt, count in sorted(rel_types.items(), key=lambda x: -x[1]):
        print(f"  {rt}: {count:,}")

    # Businesses
    with_business = [c for c in customers if "business_name" in c]
    print(f"\nBusiness Records: {len(with_business):,}")

    unique_businesses = set(c.get("business_name") for c in with_business if c.get("business_name"))
    print(f"Unique Businesses: {len(unique_businesses):,}")

    # High movers (2+)
    high_movers = [c for c in customers if c["move_count"] >= 2]
    print(f"\nHigh Movers (2+ moves): {len(high_movers):,}")

    # Nevada customers who moved twice (the demo query)
    nv_twice = [c for c in customers if c["state"] == "NV" and c["move_count"] >= 2]
    print(f"Nevada customers with 2+ moves: {len(nv_twice):,}")

    # California high movers
    ca_twice = [c for c in customers if c["state"] == "CA" and c["move_count"] >= 2]
    print(f"California customers with 2+ moves: {len(ca_twice):,}")

    # Texas high movers
    tx_twice = [c for c in customers if c["state"] == "TX" and c["move_count"] >= 2]
    print(f"Texas customers with 2+ moves: {len(tx_twice):,}")

def main():
    # Set seed for reproducibility (optional - comment out for random each time)
    # random.seed(42)

    # Generate 50K dataset
    customers = generate_dataset(50000)

    # Save to JSON
    output_file = "customer_data.json"
    print(f"\nSaving to {output_file}...")
    with open(output_file, "w") as f:
        json.dump(customers, f, indent=2)

    # Calculate file size
    import os
    file_size = os.path.getsize(output_file)
    print(f"[OK] Saved to {output_file}")
    print(f"  File size: {file_size / (1024*1024):.1f} MB")

    # Print stats
    print_stats(customers)

    # Sample records
    print("\n" + "=" * 70)
    print("SAMPLE RECORDS")
    print("=" * 70)

    # Show a regular customer
    regular = next((c for c in customers if "related_crid" not in c and "business_name" not in c), customers[0])
    print(f"\nRegular Customer:")
    print(f"  {regular['crid']}: {regular['name']}")
    print(f"  {regular['address']}, {regular['city']}, {regular['state']} {regular['zip']}")
    print(f"  Type: {regular['customer_type']} | Status: {regular['status']}")
    print(f"  Moves: {regular['move_count']} | Last: {regular['last_move']}")

    # Show a household member
    household_member = next((c for c in customers if "related_crid" in c), None)
    if household_member:
        print(f"\nHousehold Member:")
        print(f"  {household_member['crid']}: {household_member['name']}")
        print(f"  {household_member['address']}, {household_member['city']}, {household_member['state']} {household_member['zip']}")
        print(f"  Related to: {household_member['related_crid']} ({household_member['relationship_type']})")

    # Show a business
    business = next((c for c in customers if "business_name" in c), None)
    if business:
        print(f"\nBusiness Customer:")
        print(f"  {business['crid']}: {business['name']}")
        print(f"  Business: {business['business_name']}")
        print(f"  {business['address']}, {business['city']}, {business['state']} {business['zip']}")
        if "branch_count" in business:
            print(f"  Branches: {business['branch_count']}")

    # Show high mover
    high_mover = next((c for c in customers if c["move_count"] >= 4), None)
    if high_mover:
        print(f"\nHigh Mover (4+ moves):")
        print(f"  {high_mover['crid']}: {high_mover['name']}")
        print(f"  Current: {high_mover['city']}, {high_mover['state']}")
        print(f"  Total Moves: {high_mover['move_count']}")
        print(f"  Move History:")
        for move in high_mover["move_history"][:3]:
            print(f"    - {move['move_date']}: {move['city']}, {move['state']}")

if __name__ == "__main__":
    main()
