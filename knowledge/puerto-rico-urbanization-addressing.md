# Puerto Rico Urbanization Addressing Standards

**Category:** address-standards  
**Tags:** puerto-rico, urbanization, usps, addressing, zip-codes, postal  
**Source:** USPS Publication 28 - Postal Addressing Standards  
**Last Updated:** 2025-01-13  

---

## Overview

Puerto Rico addresses require special handling due to the **urbanization** field, which is unique to the island and does not exist in standard mainland U.S. addressing. The urbanization (Spanish: urbanización) identifies a specific subdivision, sector, or development within a geographic area.

## The Core Problem

In Puerto Rico, multiple addresses can have the same street name, house number, and ZIP code but be located in different subdivisions. Without the urbanization name, mail cannot be reliably delivered. This is fundamentally different from mainland U.S. addressing where street + number + ZIP is typically unique.

## Urbanization Definition

**Urbanization** denotes an area, sector, or development within a geographic area. The URB descriptor is commonly used in urban areas of Puerto Rico and is a critical component of the addressing format as it describes the location of a given street.

## ZIP Code Detection

Puerto Rico addresses are identified by ZIP codes starting with prefixes 006, 007, 008, or 009. Any address with these ZIP code prefixes may require an urbanization field.

```
ZIP Code Pattern: ^00[6-9]\d{2}(-\d{4})?$
Examples: 00926, 00917-1234, 00601, 00795
```

## Address Format Comparison

### Standard Mainland U.S. Format (3 lines):
```
RECIPIENT NAME
STREET ADDRESS [UNIT]
CITY STATE ZIP
```

### Puerto Rico Format with Urbanization (4 lines):
```
RECIPIENT NAME
URB [URBANIZATION NAME]
[STREET ADDRESS]
CITY PR ZIP
```

## Practical Examples

### Example 1: Residential with Urbanization
```
MARIA RODRIGUEZ
URB LAS GLADIOLAS
123 CALLE BEGONIA
SAN JUAN PR 00926
```

### Example 2: Apartment Building
```
JUAN SANTOS
URB VILLA NEVAREZ
APT 4B CALLE PALMA
RIO PIEDRAS PR 00927
```

### Example 3: Condominium without Street Name
Some condominiums do not have a named street. The condominium name substitutes for the street name:
```
CARLOS RIVERA
URB CONDADO
COND ASHFORD PALACE APT 502
SAN JUAN PR 00907
```

## Spanish Address Terminology

Puerto Rico uses Spanish address terminology that differs from mainland conventions:

| Spanish Term | English Equivalent | Abbreviation |
|-------------|-------------------|--------------|
| CALLE | Street | - |
| AVENIDA | Avenue | AVE |
| URBANIZACIÓN | Urbanization/Subdivision | URB |
| APARTAMENTO | Apartment | APT |
| EDIFICIO | Building | EDIF |
| RESIDENCIAL | Public Housing Project | RES |
| CONDOMINIO | Condominium | COND |

The word CALLE is commonly placed BEFORE the street name and number, which is proper Spanish composition. Example: "CALLE BEGONIA 123" rather than "123 BEGONIA ST".

## Special Cases

### Public Housing Projects (Residenciales)
Public housing projects may not have street names or may have repetitive apartment numbers. In these cases:
- The apartment number becomes the primary number
- The housing project name becomes the street name

```
JOSE MARTINEZ
APT 234 RES MANUEL A PEREZ
SAN JUAN PR 00915
```

### Areas Without Street Names
Some areas lack street names or have repetitive house numbers. The urbanization name substitutes as the street name and becomes the primary identifier.

## Algorithm for Address Processing

### Detection Logic
```python
def is_puerto_rico_address(zip_code: str) -> bool:
    """Determine if address is Puerto Rico based on ZIP prefix."""
    if not zip_code or len(zip_code) < 3:
        return False
    prefix = zip_code[:3]
    return prefix in ('006', '007', '008', '009')
```

### Validation Logic
```python
def validate_pr_address(address: dict) -> dict:
    """Validate Puerto Rico address and flag missing urbanization."""
    result = {'valid': True, 'warnings': []}
    
    if is_puerto_rico_address(address.get('zip_code', '')):
        if not address.get('urbanization'):
            result['warnings'].append(
                'Puerto Rico address without urbanization - verify deliverability'
            )
    return result
```

### Formatting Logic
```python
def format_address(address: dict) -> str:
    """Format address with Puerto Rico urbanization support."""
    lines = [address['name']]
    
    # Insert urbanization line for Puerto Rico
    if is_puerto_rico_address(address.get('zip_code', '')):
        if address.get('urbanization'):
            lines.append(f"URB {address['urbanization']}")
    
    lines.append(address['street_address'])
    lines.append(f"{address['city']} {address['state']} {address['zip_code']}")
    
    return '\n'.join(lines)
```

## Database Schema Considerations

When storing addresses that may include Puerto Rico, add a nullable urbanization field:

```sql
CREATE TABLE addresses (
    id INT PRIMARY KEY,
    recipient_name VARCHAR(100) NOT NULL,
    urbanization VARCHAR(50) NULL,      -- Puerto Rico only (ZIP 006-009)
    street_address VARCHAR(100) NOT NULL,
    secondary_unit VARCHAR(20) NULL,    -- APT, UNIT, etc.
    city VARCHAR(50) NOT NULL,
    state CHAR(2) NOT NULL,
    zip_code VARCHAR(10) NOT NULL,
    
    CONSTRAINT chk_urbanization CHECK (
        urbanization IS NULL OR 
        LEFT(zip_code, 3) IN ('006', '007', '008', '009')
    )
);
```

## API Response Structure

When returning Puerto Rico addresses via API, include the urbanization as a distinct field:

```json
{
  "address": {
    "recipient": "MARIA RODRIGUEZ",
    "urbanization": "LAS GLADIOLAS",
    "street": "123 CALLE BEGONIA",
    "city": "SAN JUAN",
    "state": "PR",
    "zip": "00926",
    "is_puerto_rico": true
  }
}
```

## USPS Integration Notes

1. **Address Validation**: When validating against USPS Address Management System (AMS), Puerto Rico addresses must include urbanization for accurate matching.

2. **ZIP+4 Lookup**: The urbanization name is often required to get accurate ZIP+4 codes in Puerto Rico.

3. **Standardization**: USPS uses English equivalents in the ZIP+4 file, so normalize Spanish terms during processing.

4. **Character Restrictions**: Special characters (ñ, é, í, ó, ú, ü, ¿, ¡) should be replaced with Roman alphabet equivalents for USPS compatibility.

## Summary

The key insight for handling Puerto Rico addresses: **Urbanization is a mandatory disambiguation field that identifies which subdivision contains the address.** Without it, the same street address in the same ZIP code could refer to multiple locations.

When building address handling systems:
1. Detect Puerto Rico by ZIP prefix (006-009)
2. Add urbanization field to data model
3. Place URB line between name and street address
4. Flag addresses missing urbanization for review
5. Handle Spanish terminology (CALLE before street name)
