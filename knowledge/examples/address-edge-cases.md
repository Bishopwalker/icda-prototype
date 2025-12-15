---
tags: [edge-cases, validation, testing]
---

# Address Edge Cases and Validation Rules

This document covers common edge cases encountered during address verification.

## Military Addresses (APO/FPO/DPO)

Military addresses use special formats:
- **APO** - Army Post Office (Europe, Pacific)
- **FPO** - Fleet Post Office (Navy, Marine Corps)
- **DPO** - Diplomatic Post Office

Example military addresses:
```
PFC John Smith
Unit 12345 Box 6789
APO AE 09012

LCDR Jane Doe
USS Enterprise (CVN-65)
FPO AP 96601
```

## PO Box Addresses

PO Boxes should not have street addresses mixed:
- Valid: `PO Box 1234, City, ST 12345`
- Invalid: `123 Main St, PO Box 1234, City, ST 12345`

## Rural Route Addresses

Legacy rural routes are being phased out:
- Old format: `RR 2 Box 45`
- New format: `1234 County Road 56`

## Unit/Apartment Designators

USPS preferred format uses # symbol:
- Preferred: `123 Main St #4B`
- Acceptable: `123 Main St Apt 4B`
- Acceptable: `123 Main St Unit 4B`

## Directional Prefixes

Directionals can be tricky:
- `123 N Main St` - North Main Street
- `123 North Main St` - Same address
- `123 Main St N` - Main Street North (different!)

## ZIP Code Rules

- Standard ZIP: 5 digits (12345)
- ZIP+4: 9 digits with hyphen (12345-6789)
- Puerto Rico: 006xx-009xx range
- Virgin Islands: 008xx range
- Military: Varies by region

## Common Parsing Errors

1. **Street type confusion**: "Oak Lane" vs "Oak Ln" vs "Oakland"
2. **City/State ambiguity**: "Kansas City, KS" vs "Kansas City, MO"
3. **Numeric street names**: "42nd St" vs "Forty Second Street"
4. **Spanish names**: "Calle Luna" should not extract "Luna" as city
