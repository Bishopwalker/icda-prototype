# Puerto Rico Address Examples

Test cases and examples for Puerto Rico address verification.

## Valid PR Addresses with Urbanization

### Example 1: Standard Residential
```
MARIA RODRIGUEZ
URB LAS GLADIOLAS
123 CALLE BEGONIA
SAN JUAN PR 00926
```
- **ZIP**: 00926 (PR prefix 009)
- **Urbanization**: LAS GLADIOLAS
- **Street**: CALLE BEGONIA 123

### Example 2: Apartment in Urbanization
```
JUAN SANTOS
URB VILLA NEVAREZ
APT 4B CALLE PALMA
RIO PIEDRAS PR 00927
```
- **ZIP**: 00927
- **Urbanization**: VILLA NEVAREZ
- **Unit**: APT 4B

### Example 3: Condominium
```
CARLOS RIVERA
URB CONDADO
COND ASHFORD PALACE APT 502
SAN JUAN PR 00907
```
- **ZIP**: 00907
- **Urbanization**: CONDADO
- **Building**: COND ASHFORD PALACE

### Example 4: Residencial (Public Housing)
```
ANA MARTINEZ
RES LUIS LLORENS TORRES
APT 123 EDIF 5
SAN JUAN PR 00924
```
- **ZIP**: 00924
- **Urbanization**: Type is RESIDENCIAL
- **Building**: EDIF 5, APT 123

### Example 5: Spanish Format with CALLE prefix
```
JOSE GARCIA
URBANIZACION SANTA ROSA
CALLE ROSA 45
BAYAMON PR 00961
```
- **ZIP**: 00961
- **Urbanization**: SANTA ROSA (from URBANIZACION keyword)
- **Street**: CALLE ROSA 45

## PR Addresses Missing Urbanization (INVALID)

### Example 6: Missing URB - Ambiguous
```
JOSE MARTINEZ
123 CALLE PRINCIPAL
SAN JUAN PR 00926
```
**Issue**: Multiple subdivisions in ZIP 00926 may have "CALLE PRINCIPAL"
**Required**: Add URB [name] to disambiguate

### Example 7: ZIP-Only Address
```
MARIA LOPEZ
456 AVENIDA ASHFORD
00907
```
**Issue**: Missing city, state, and urbanization
**Required**: Full PR format with URB

## Test Case Matrix

| Raw Input | Expected URB | Expected City | Expected ZIP | PR Detected | Valid |
|-----------|--------------|---------------|--------------|-------------|-------|
| `URB LAS GLADIOLAS 123 CALLE BEGONIA SAN JUAN PR 00926` | LAS GLADIOLAS | SAN JUAN | 00926 | Yes | Yes |
| `URBANIZACION VILLA NEVAREZ APT 4B RIO PIEDRAS 00927` | VILLA NEVAREZ | RIO PIEDRAS | 00927 | Yes | Yes |
| `123 CALLE PALMA SAN JUAN 00927` | null | SAN JUAN | 00927 | Yes | No (missing URB) |
| `URB CONDADO COND PALACE APT 5 SAN JUAN PR 00907` | CONDADO | SAN JUAN | 00907 | Yes | Yes |
| `123 MAIN ST SPRINGFIELD VA 22222` | null | SPRINGFIELD | 22222 | No | Yes (not PR) |

## ZIP Code Ranges for Puerto Rico

| Prefix | Range | Notes |
|--------|-------|-------|
| 006 | 00601-00693 | Western PR |
| 007 | 00700-00799 | San Juan metro |
| 008 | 00800-00899 | Northern PR |
| 009 | 00900-00988 | San Juan, eastern PR |

## Parsing Priority

1. **Extract ZIP first** - Most reliable anchor (006-009 prefix = PR)
2. **Detect urbanization keyword** - URB, URBANIZACION, URBANIZACIÓN
3. **Extract urbanization name** - Text after URB until street indicator
4. **Parse street** - CALLE, AVE, AVENIDA prefixes common
5. **Extract city/state** - PR assumed if ZIP detected

## Common Spanish Terms

| Spanish | English | Usage |
|---------|---------|-------|
| CALLE | Street | Prefix before street name |
| AVENIDA/AVE | Avenue | Street type |
| URBANIZACION/URB | Urbanization | Required PR field |
| APARTAMENTO/APT | Apartment | Unit type |
| EDIFICIO/EDIF | Building | Building identifier |
| RESIDENCIAL/RES | Public housing | Housing project type |
| CONDOMINIO/COND | Condominium | Building type |

## Batch Processing Examples

### Input Batch (40 addresses)
```json
[
  {"id": "1", "address": "URB LAS GLADIOLAS 123 CALLE BEGONIA SAN JUAN PR 00926"},
  {"id": "2", "address": "URB VILLA NEVAREZ APT 4B RIO PIEDRAS 00927"},
  {"id": "3", "address": "123 CALLE PALMA SAN JUAN 00926"},
  ...
]
```

### Expected Output
```json
[
  {"id": "1", "status": "verified", "urbanization": "LAS GLADIOLAS", "confidence": 0.95},
  {"id": "2", "status": "verified", "urbanization": "VILLA NEVAREZ", "confidence": 0.92},
  {"id": "3", "status": "needs_review", "urbanization": null, "warning": "PR address missing urbanization"},
  ...
]
```
