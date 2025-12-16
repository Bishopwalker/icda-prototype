# ICDA Knowledge Base

Internal documentation for the ICDA (Intelligent Customer Data Access) system.
This folder is automatically indexed by the MCP Knowledge Server for RAG retrieval.

## Folder Structure

```
knowledge/
├── README.md                    # This file
├── address-standards/           # Address format standards and rules
│   ├── puerto-rico-urbanization-addressing.md
│   └── usps-address-format-standards.md (planned)
├── patterns/                    # Domain patterns and validation rules
│   ├── pr-urbanization-patterns.md (planned)
│   ├── verification-rules.md (planned)
│   └── error-handling-patterns.md (planned)
├── examples/                    # Query and address examples
│   ├── address-query-examples.md (planned)
│   ├── verification-examples.md (planned)
│   └── edge-cases.md (planned)
└── api/                         # API documentation
    └── icda-endpoints.md (planned)
```

## Document Categories

### address-standards
Official address format standards including:
- Puerto Rico urbanization rules (ZIP 006-009)
- USPS address formatting guidelines
- State-specific address quirks

### patterns
Domain patterns for address verification:
- PR urbanization detection patterns
- Validation rule definitions
- Error handling strategies

### examples
Practical examples for testing and reference:
- NLP query examples
- Address verification input/output pairs
- Edge cases and complex scenarios

### api
API documentation for developers:
- REST endpoint reference
- Nova tool calling schemas
- Guardrails configuration

## Auto-Indexing

Documents in this folder are automatically indexed when:
1. The MCP Knowledge Server starts
2. The main ICDA application starts (via `main.py`)
3. A document is uploaded via MCP tools

### Supported Formats
- Markdown (.md) - Preferred
- Plain text (.txt)
- PDF (.pdf)
- Word documents (.docx)

### Document Best Practices

1. **Use descriptive filenames**: `puerto-rico-urbanization-addressing.md` not `pr-addr.md`
2. **Add frontmatter tags**: Help with filtering and categorization
3. **Include examples**: Concrete examples improve RAG retrieval
4. **Keep chunks reasonable**: Avoid very long paragraphs

### Frontmatter Example

```markdown
---
title: Puerto Rico Urbanization Addressing
category: address-standards
tags:
  - puerto-rico
  - urbanization
  - usps
  - zip-codes
---
```

## Usage with MCP Knowledge Server

```bash
# Search for PR urbanization rules
search_knowledge(query="how to detect puerto rico addresses", tags=["puerto-rico"])

# List all address standards
list_documents(category="address-standards")

# Upload new document
upload_document(file_path="/path/to/doc.md", category="patterns", tags=["validation"])
```

## Related Files

- `.mcp.json` - MCP server configuration
- `mcp-knowledge-server/` - Knowledge server implementation
- `icda/knowledge.py` - ICDA knowledge manager
- `main.py` - Auto-indexing on startup
