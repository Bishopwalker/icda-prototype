"""
Document Processor - Extract and chunk content from various file formats.

Supports:
  - Plain text (.txt)
  - Markdown (.md)
  - PDF (.pdf)
  - Word documents (.docx)
  - JSON (.json)
"""

import json
import re
from pathlib import Path
from typing import Any

import tiktoken


class DocumentProcessor:
    """Process documents into embeddable chunks."""
    
    # Chunk settings
    CHUNK_SIZE = 512  # tokens
    CHUNK_OVERLAP = 50  # tokens
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    def process_file(self, path: Path) -> list[dict]:
        """
        Process a file into chunks.
        
        Args:
            path: Path to the file
            
        Returns:
            List of {"text": str, "metadata": dict}
        """
        suffix = path.suffix.lower()
        
        try:
            if suffix == ".txt":
                content = self._read_text(path)
            elif suffix == ".md":
                content = self._read_markdown(path)
            elif suffix == ".pdf":
                content = self._read_pdf(path)
            elif suffix == ".docx":
                content = self._read_docx(path)
            elif suffix == ".json":
                content = self._read_json(path)
            else:
                # Try as plain text
                content = self._read_text(path)
        except Exception as e:
            print(f"Error reading {path}: {e}")
            return []
        
        if not content:
            return []
        
        return self.chunk_text(content, path.name)
    
    def chunk_text(self, content: str, source_name: str = "unknown") -> list[dict]:
        """
        Split content into overlapping chunks.
        
        Uses semantic chunking - tries to break at paragraph/sentence boundaries.
        
        Args:
            content: Text content to chunk
            source_name: Source identifier for metadata
            
        Returns:
            List of {"text": str, "metadata": dict}
        """
        # Clean content
        content = self._clean_text(content)
        
        if not content:
            return []
        
        # Split into paragraphs first
        paragraphs = re.split(r'\n\s*\n', content)
        
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            para_tokens = len(self.tokenizer.encode(para))
            
            # If single paragraph exceeds chunk size, split it
            if para_tokens > self.chunk_size:
                # Flush current chunk first
                if current_chunk:
                    chunks.append(self._make_chunk(current_chunk, source_name, len(chunks)))
                    current_chunk = []
                    current_tokens = 0
                
                # Split large paragraph by sentences
                sentences = self._split_sentences(para)
                for sent in sentences:
                    sent_tokens = len(self.tokenizer.encode(sent))
                    
                    if current_tokens + sent_tokens > self.chunk_size:
                        if current_chunk:
                            chunks.append(self._make_chunk(current_chunk, source_name, len(chunks)))
                        # Start new chunk with overlap
                        overlap_text = self._get_overlap(current_chunk)
                        current_chunk = [overlap_text] if overlap_text else []
                        current_tokens = len(self.tokenizer.encode(overlap_text)) if overlap_text else 0
                    
                    current_chunk.append(sent)
                    current_tokens += sent_tokens
            
            # Normal paragraph - add to current chunk
            elif current_tokens + para_tokens > self.chunk_size:
                # Chunk full, start new one
                chunks.append(self._make_chunk(current_chunk, source_name, len(chunks)))
                
                # Start new chunk with overlap
                overlap_text = self._get_overlap(current_chunk)
                current_chunk = [overlap_text, para] if overlap_text else [para]
                current_tokens = len(self.tokenizer.encode(" ".join(current_chunk)))
            else:
                current_chunk.append(para)
                current_tokens += para_tokens
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append(self._make_chunk(current_chunk, source_name, len(chunks)))
        
        return chunks
    
    def _make_chunk(self, parts: list[str], source: str, index: int) -> dict:
        """Create a chunk dict."""
        text = "\n\n".join(p for p in parts if p)
        return {
            "text": text,
            "metadata": {
                "source": source,
                "chunk_index": index,
                "char_count": len(text),
                "token_count": len(self.tokenizer.encode(text))
            }
        }
    
    def _get_overlap(self, parts: list[str]) -> str:
        """Get overlap text from end of chunk."""
        if not parts:
            return ""
        
        # Take last paragraph or portion thereof
        last = parts[-1]
        tokens = self.tokenizer.encode(last)
        
        if len(tokens) <= self.chunk_overlap:
            return last
        
        # Take last N tokens
        return self.tokenizer.decode(tokens[-self.chunk_overlap:])
    
    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Remove null bytes and other control characters
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
        
        return text.strip()
    
    # ============== File Readers ==============
    
    def _read_text(self, path: Path) -> str:
        """Read plain text file."""
        return path.read_text(encoding="utf-8", errors="ignore")
    
    def _read_markdown(self, path: Path) -> str:
        """Read markdown file (preserves structure)."""
        content = path.read_text(encoding="utf-8", errors="ignore")
        
        # Optionally convert to plain text (removing markdown syntax)
        # For now, keep markdown - embeddings work well with it
        return content
    
    def _read_pdf(self, path: Path) -> str:
        """Read PDF file."""
        try:
            from pypdf import PdfReader
            
            reader = PdfReader(path)
            text_parts = []
            
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            
            return "\n\n".join(text_parts)
        except ImportError:
            print("pypdf not installed. Run: pip install pypdf")
            return ""
        except Exception as e:
            print(f"PDF read error: {e}")
            return ""
    
    def _read_docx(self, path: Path) -> str:
        """Read Word document."""
        try:
            from docx import Document
            
            doc = Document(path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            
            return "\n\n".join(paragraphs)
        except ImportError:
            print("python-docx not installed. Run: pip install python-docx")
            return ""
        except Exception as e:
            print(f"DOCX read error: {e}")
            return ""
    
    def _read_json(self, path: Path) -> str:
        """Read JSON file (converts to readable text)."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return self._json_to_text(data)
        except Exception as e:
            print(f"JSON read error: {e}")
            return ""
    
    def _json_to_text(self, data: Any, prefix: str = "") -> str:
        """Convert JSON structure to readable text."""
        if isinstance(data, dict):
            parts = []
            for key, value in data.items():
                key_str = f"{prefix}{key}" if prefix else key
                
                if isinstance(value, (dict, list)):
                    parts.append(f"{key_str}:")
                    parts.append(self._json_to_text(value, "  "))
                else:
                    parts.append(f"{key_str}: {value}")
            return "\n".join(parts)
        
        elif isinstance(data, list):
            parts = []
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)):
                    parts.append(f"{prefix}[{i}]:")
                    parts.append(self._json_to_text(item, prefix + "  "))
                else:
                    parts.append(f"{prefix}- {item}")
            return "\n".join(parts)
        
        else:
            return str(data)


# ============== CLI for Testing ==============

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python document_processor.py <file_path>")
        sys.exit(1)
    
    processor = DocumentProcessor()
    path = Path(sys.argv[1])
    
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)
    
    chunks = processor.process_file(path)
    
    print(f"\n📄 Processed: {path.name}")
    print(f"   Chunks: {len(chunks)}")
    
    for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i} ({chunk['metadata']['token_count']} tokens) ---")
        print(chunk["text"][:300] + "..." if len(chunk["text"]) > 300 else chunk["text"])
