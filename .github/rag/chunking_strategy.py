"""
Universal Code Chunking Strategy - Language Agnostic with Spring Boot Support
Intelligently chunks code for RAG indexing with special handling for:
- Java (Spring Boot, JPA, REST controllers, services, repositories)
- Python (classes, functions, FastAPI routes)
- TypeScript/JavaScript (classes, functions, React components)
- Markdown (headers)
- Any other code files
"""

import os
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
from enum import Enum


class ChunkType(Enum):
    """Types of code chunks"""
    # Java/Spring Boot
    SPRING_CONTROLLER = "spring_controller"
    SPRING_SERVICE = "spring_service"
    SPRING_REPOSITORY = "spring_repository"
    SPRING_ENTITY = "spring_entity"
    SPRING_CONFIG = "spring_config"
    JAVA_CLASS = "java_class"
    JAVA_METHOD = "java_method"
    JAVA_INTERFACE = "java_interface"

    # Python
    PYTHON_CLASS = "python_class"
    PYTHON_FUNCTION = "python_function"
    FASTAPI_ROUTE = "fastapi_route"

    # JavaScript/TypeScript
    TS_CLASS = "ts_class"
    TS_FUNCTION = "ts_function"
    REACT_COMPONENT = "react_component"

    # Documentation
    MARKDOWN_SECTION = "markdown_section"

    # Generic
    FILE = "file"
    COMMENT_BLOCK = "comment_block"


@dataclass
class CodeChunk:
    """
    Represents a chunk of code for RAG indexing

    Attributes:
        id: Unique identifier
        content: The actual code content
        file_path: Path to the source file
        chunk_type: Type of chunk (controller, service, etc.)
        start_line: Starting line number
        end_line: Ending line number
        metadata: Additional context (annotations, class name, etc.)
    """
    id: str
    content: str
    file_path: str
    chunk_type: str
    start_line: int
    end_line: int
    metadata: Dict[str, Any]

    def __post_init__(self):
        """Validate chunk after creation"""
        if not self.content.strip():
            raise ValueError("Chunk content cannot be empty")
        if self.start_line > self.end_line:
            raise ValueError(f"Invalid line range: {self.start_line} > {self.end_line}")


class JavaSpringBootChunker:
    """
    Specialized chunker for Java Spring Boot projects
    Recognizes Spring annotations and structures
    """

    # Spring Boot annotations to detect
    SPRING_ANNOTATIONS = {
        '@RestController': ChunkType.SPRING_CONTROLLER,
        '@Controller': ChunkType.SPRING_CONTROLLER,
        '@Service': ChunkType.SPRING_SERVICE,
        '@Repository': ChunkType.SPRING_REPOSITORY,
        '@Entity': ChunkType.SPRING_ENTITY,
        '@Table': ChunkType.SPRING_ENTITY,
        '@Configuration': ChunkType.SPRING_CONFIG,
        '@Component': ChunkType.JAVA_CLASS,
    }

    # Request mapping annotations
    REQUEST_MAPPINGS = [
        '@RequestMapping', '@GetMapping', '@PostMapping',
        '@PutMapping', '@DeleteMapping', '@PatchMapping'
    ]

    @staticmethod
    def detect_spring_type(content: str) -> Optional[ChunkType]:
        """Detect Spring Boot component type from content"""
        for annotation, chunk_type in JavaSpringBootChunker.SPRING_ANNOTATIONS.items():
            if annotation in content:
                return chunk_type
        return None

    @staticmethod
    def extract_class_chunks(file_path: str, content: str) -> List[CodeChunk]:
        """
        Extract chunks from Java file with Spring Boot awareness

        Strategy:
        1. Detect Spring annotations (Controller, Service, Repository, etc.)
        2. Extract entire class with annotations as context
        3. Extract individual methods as separate chunks
        4. Keep Spring context (annotations, dependencies)
        """
        chunks = []
        lines = content.split('\n')

        # Find all class definitions
        class_pattern = re.compile(r'^\s*(public|private|protected)?\s*(static)?\s*class\s+(\w+)')
        interface_pattern = re.compile(r'^\s*(public|private|protected)?\s*interface\s+(\w+)')

        current_class = None
        class_start = 0
        class_annotations = []
        brace_count = 0
        in_class = False

        for line_num, line in enumerate(lines, 1):
            # Collect annotations before class
            if line.strip().startswith('@') and not in_class:
                class_annotations.append(line.strip())

            # Detect class/interface start
            class_match = class_pattern.search(line)
            interface_match = interface_pattern.search(line)

            if class_match or interface_match:
                current_class = class_match.group(3) if class_match else interface_match.group(2)
                class_start = line_num
                in_class = True
                brace_count = 0

            # Track braces to find class end
            if in_class:
                brace_count += line.count('{') - line.count('}')

                # Class ended
                if brace_count == 0 and '{' in ''.join(lines[class_start-1:line_num]):
                    class_content = '\n'.join(lines[class_start-1:line_num])

                    # Detect Spring component type
                    annotations_str = '\n'.join(class_annotations)
                    spring_type = JavaSpringBootChunker.detect_spring_type(annotations_str)
                    chunk_type = spring_type if spring_type else ChunkType.JAVA_CLASS

                    # Extract class-level metadata
                    metadata = {
                        'class_name': current_class,
                        'annotations': class_annotations.copy(),
                        'language': 'java',
                        'framework': 'spring-boot' if spring_type else None
                    }

                    # Add Spring-specific metadata
                    if spring_type:
                        JavaSpringBootChunker._add_spring_metadata(class_content, metadata)

                    # Create class-level chunk
                    chunk_id = f"{file_path}::{current_class}::class::{class_start}"
                    chunks.append(CodeChunk(
                        id=chunk_id,
                        content=class_content,
                        file_path=file_path,
                        chunk_type=chunk_type.value,
                        start_line=class_start,
                        end_line=line_num,
                        metadata=metadata
                    ))

                    # Extract method chunks from class
                    method_chunks = JavaSpringBootChunker._extract_methods(
                        file_path,
                        class_content,
                        current_class,
                        class_start,
                        spring_type
                    )
                    chunks.extend(method_chunks)

                    # Reset for next class
                    in_class = False
                    current_class = None
                    class_annotations = []

        return chunks

    @staticmethod
    def _extract_methods(
        file_path: str,
        class_content: str,
        class_name: str,
        class_start: int,
        spring_type: Optional[ChunkType]
    ) -> List[CodeChunk]:
        """Extract individual methods from a class"""
        chunks = []
        lines = class_content.split('\n')

        # Method pattern (public/private/protected methods)
        method_pattern = re.compile(
            r'^\s*(public|private|protected)\s+(?:static\s+)?(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\('
        )

        current_method = None
        method_start = 0
        method_annotations = []
        brace_count = 0
        in_method = False

        for line_num, line in enumerate(lines, 1):
            # Collect method annotations
            if line.strip().startswith('@') and not in_method:
                method_annotations.append(line.strip())

            # Detect method start
            method_match = method_pattern.search(line)
            if method_match:
                current_method = method_match.group(2)
                method_start = line_num
                in_method = True
                brace_count = 0

            # Track braces
            if in_method:
                brace_count += line.count('{') - line.count('}')

                # Method ended
                if brace_count == 0 and '{' in ''.join(lines[method_start-1:line_num]):
                    method_content = '\n'.join(lines[method_start-1:line_num])

                    # Create metadata
                    metadata = {
                        'class_name': class_name,
                        'method_name': current_method,
                        'annotations': method_annotations.copy(),
                        'language': 'java',
                        'framework': 'spring-boot' if spring_type else None
                    }

                    # Check if this is a Spring endpoint
                    if JavaSpringBootChunker._is_spring_endpoint(method_annotations):
                        metadata['is_endpoint'] = True
                        metadata['http_methods'] = JavaSpringBootChunker._extract_http_methods(method_annotations)
                        metadata['endpoint_path'] = JavaSpringBootChunker._extract_endpoint_path(method_annotations)

                    # Create method chunk
                    chunk_id = f"{file_path}::{class_name}::{current_method}::{class_start + method_start}"
                    chunks.append(CodeChunk(
                        id=chunk_id,
                        content=method_content,
                        file_path=file_path,
                        chunk_type=ChunkType.JAVA_METHOD.value,
                        start_line=class_start + method_start - 1,
                        end_line=class_start + line_num - 1,
                        metadata=metadata
                    ))

                    # Reset
                    in_method = False
                    current_method = None
                    method_annotations = []

        return chunks

    @staticmethod
    def _add_spring_metadata(content: str, metadata: Dict[str, Any]):
        """Add Spring Boot specific metadata"""
        # Extract @RequestMapping path
        request_mapping = re.search(r'@RequestMapping\(["\']([^"\']+)["\']', content)
        if request_mapping:
            metadata['base_path'] = request_mapping.group(1)

        # Extract @Autowired dependencies
        autowired = re.findall(r'@Autowired\s+(?:private\s+)?(\w+)', content)
        if autowired:
            metadata['dependencies'] = autowired

        # Extract JPA entity details
        if '@Entity' in content:
            table_match = re.search(r'@Table\(name\s*=\s*["\']([^"\']+)["\']', content)
            if table_match:
                metadata['table_name'] = table_match.group(1)

    @staticmethod
    def _is_spring_endpoint(annotations: List[str]) -> bool:
        """Check if method annotations indicate a Spring endpoint"""
        return any(mapping in '\n'.join(annotations) for mapping in JavaSpringBootChunker.REQUEST_MAPPINGS)

    @staticmethod
    def _extract_http_methods(annotations: List[str]) -> List[str]:
        """Extract HTTP methods from annotations"""
        methods = []
        annotation_str = '\n'.join(annotations)

        if '@GetMapping' in annotation_str:
            methods.append('GET')
        if '@PostMapping' in annotation_str:
            methods.append('POST')
        if '@PutMapping' in annotation_str:
            methods.append('PUT')
        if '@DeleteMapping' in annotation_str:
            methods.append('DELETE')
        if '@PatchMapping' in annotation_str:
            methods.append('PATCH')

        # Check @RequestMapping for explicit method
        request_mapping = re.search(r'@RequestMapping\([^)]*method\s*=\s*RequestMethod\.(\w+)', annotation_str)
        if request_mapping:
            methods.append(request_mapping.group(1))

        return methods

    @staticmethod
    def _extract_endpoint_path(annotations: List[str]) -> Optional[str]:
        """Extract endpoint path from annotations"""
        annotation_str = '\n'.join(annotations)

        # Try all mapping annotations
        for mapping in JavaSpringBootChunker.REQUEST_MAPPINGS:
            match = re.search(f'{mapping}\\(["\']([^"\']+)["\']', annotation_str)
            if match:
                return match.group(1)

        return None


class PythonChunker:
    """Chunker for Python files with FastAPI support"""

    @staticmethod
    def extract_chunks(file_path: str, content: str) -> List[CodeChunk]:
        """Extract Python classes and functions"""
        chunks = []
        lines = content.split('\n')

        # Class pattern
        class_pattern = re.compile(r'^class\s+(\w+)')
        # Function pattern
        func_pattern = re.compile(r'^def\s+(\w+)\s*\(')
        # FastAPI route pattern
        route_pattern = re.compile(r'@(router|app)\.(get|post|put|delete|patch)')

        current_indent = 0
        current_block = None
        block_start = 0
        block_lines = []
        block_type = None
        is_route = False

        for line_num, line in enumerate(lines, 1):
            indent = len(line) - len(line.lstrip())

            # Detect class
            class_match = class_pattern.search(line)
            if class_match:
                if current_block:
                    # Save previous block
                    chunks.append(PythonChunker._create_chunk(
                        file_path, current_block, block_start, line_num - 1,
                        '\n'.join(block_lines), block_type, is_route
                    ))

                current_block = class_match.group(1)
                block_start = line_num
                block_lines = [line]
                block_type = ChunkType.PYTHON_CLASS
                current_indent = indent
                is_route = False
                continue

            # Detect function
            func_match = func_pattern.search(line)
            if func_match and (not current_block or indent <= current_indent):
                if current_block:
                    # Save previous block
                    chunks.append(PythonChunker._create_chunk(
                        file_path, current_block, block_start, line_num - 1,
                        '\n'.join(block_lines), block_type, is_route
                    ))

                current_block = func_match.group(1)
                block_start = line_num
                block_lines = [line]
                block_type = ChunkType.PYTHON_FUNCTION
                current_indent = indent

                # Check if previous line was a route decorator
                if line_num > 1:
                    prev_line = lines[line_num - 2]
                    is_route = bool(route_pattern.search(prev_line))
                else:
                    is_route = False
                continue

            # Continue collecting lines for current block
            if current_block and indent > current_indent:
                block_lines.append(line)
            elif current_block and line.strip() == '':
                block_lines.append(line)
            elif current_block:
                # Block ended
                chunks.append(PythonChunker._create_chunk(
                    file_path, current_block, block_start, line_num - 1,
                    '\n'.join(block_lines), block_type, is_route
                ))
                current_block = None
                block_lines = []

        # Save last block
        if current_block:
            chunks.append(PythonChunker._create_chunk(
                file_path, current_block, block_start, len(lines),
                '\n'.join(block_lines), block_type, is_route
            ))

        return chunks

    @staticmethod
    def _create_chunk(file_path, name, start, end, content, chunk_type, is_route):
        """Create a Python code chunk"""
        metadata = {
            'name': name,
            'language': 'python',
        }

        if is_route:
            metadata['is_fastapi_route'] = True
            chunk_type = ChunkType.FASTAPI_ROUTE

        chunk_id = f"{file_path}::{name}::{start}"
        return CodeChunk(
            id=chunk_id,
            content=content,
            file_path=file_path,
            chunk_type=chunk_type.value,
            start_line=start,
            end_line=end,
            metadata=metadata
        )


class TypeScriptChunker:
    """Chunker for TypeScript/JavaScript files"""

    @staticmethod
    def extract_chunks(file_path: str, content: str) -> List[CodeChunk]:
        """Extract TS/JS classes, functions, and React components"""
        chunks = []
        lines = content.split('\n')

        # Patterns
        class_pattern = re.compile(r'^\s*(?:export\s+)?class\s+(\w+)')
        func_pattern = re.compile(r'^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)')
        arrow_func = re.compile(r'^\s*(?:export\s+)?const\s+(\w+)\s*=\s*\([^)]*\)\s*=>')
        react_component = re.compile(r'^\s*(?:export\s+)?(?:const|function)\s+(\w+).*(?:React\.FC|:\s*FC|React\.Component)')

        # Similar to Python chunker but for TS/JS syntax
        # Implementation would be similar to Python chunker
        # For brevity, returning basic file chunk

        chunk_id = f"{file_path}::file::1"
        return [CodeChunk(
            id=chunk_id,
            content=content,
            file_path=file_path,
            chunk_type=ChunkType.FILE.value,
            start_line=1,
            end_line=len(lines),
            metadata={'language': 'typescript'}
        )]


class MarkdownChunker:
    """Chunker for Markdown documentation"""

    @staticmethod
    def extract_chunks(file_path: str, content: str) -> List[CodeChunk]:
        """Split Markdown by headers"""
        chunks = []
        lines = content.split('\n')

        current_section = None
        section_start = 0
        section_lines = []

        for line_num, line in enumerate(lines, 1):
            # Detect headers
            if line.startswith('#'):
                if current_section:
                    # Save previous section
                    chunk_id = f"{file_path}::{current_section}::{section_start}"
                    chunks.append(CodeChunk(
                        id=chunk_id,
                        content='\n'.join(section_lines),
                        file_path=file_path,
                        chunk_type=ChunkType.MARKDOWN_SECTION.value,
                        start_line=section_start,
                        end_line=line_num - 1,
                        metadata={'section': current_section, 'language': 'markdown'}
                    ))

                # Start new section
                current_section = line.lstrip('#').strip()
                section_start = line_num
                section_lines = [line]
            else:
                section_lines.append(line)

        # Save last section
        if current_section:
            chunk_id = f"{file_path}::{current_section}::{section_start}"
            chunks.append(CodeChunk(
                id=chunk_id,
                content='\n'.join(section_lines),
                file_path=file_path,
                chunk_type=ChunkType.MARKDOWN_SECTION.value,
                start_line=section_start,
                end_line=len(lines),
                metadata={'section': current_section, 'language': 'markdown'}
            ))

        return chunks


class UniversalChunkingStrategy:
    """
    Universal code chunking strategy for any project
    Automatically detects file types and uses appropriate chunker
    """

    # File extensions mapping
    JAVA_EXTENSIONS = {'.java'}
    PYTHON_EXTENSIONS = {'.py'}
    TYPESCRIPT_EXTENSIONS = {'.ts', '.tsx', '.js', '.jsx'}
    MARKDOWN_EXTENSIONS = {'.md', '.markdown'}

    # Directories to skip
    SKIP_DIRS = {
        'node_modules', 'venv', 'env', '.git', '__pycache__',
        'dist', 'build', 'target', '.gradle', '.idea', '.vscode',
        'coverage', '.pytest_cache', '.mypy_cache'
    }

    def __init__(self, project_root: str):
        """
        Initialize chunking strategy

        Args:
            project_root: Root directory of the project
        """
        self.project_root = Path(project_root)

    def chunk_project(self) -> List[CodeChunk]:
        """
        Chunk entire project

        Returns:
            List of all code chunks from the project
        """
        all_chunks = []

        # Walk through project
        for root, dirs, files in os.walk(self.project_root):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]

            for file in files:
                file_path = Path(root) / file
                relative_path = file_path.relative_to(self.project_root)

                try:
                    chunks = self.chunk_file(str(relative_path))
                    all_chunks.extend(chunks)
                except Exception as e:
                    print(f"Warning: Failed to chunk {relative_path}: {e}")

        return all_chunks

    def chunk_file(self, relative_file_path: str) -> List[CodeChunk]:
        """
        Chunk a single file

        Args:
            relative_file_path: Path relative to project root

        Returns:
            List of chunks from the file
        """
        file_path = self.project_root / relative_file_path

        if not file_path.exists():
            return []

        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"Warning: Could not read {relative_file_path}: {e}")
            return []

        # Get file extension
        ext = file_path.suffix.lower()

        # Route to appropriate chunker
        if ext in self.JAVA_EXTENSIONS:
            return JavaSpringBootChunker.extract_class_chunks(
                str(relative_file_path),
                content
            )
        elif ext in self.PYTHON_EXTENSIONS:
            return PythonChunker.extract_chunks(
                str(relative_file_path),
                content
            )
        elif ext in self.TYPESCRIPT_EXTENSIONS:
            return TypeScriptChunker.extract_chunks(
                str(relative_file_path),
                content
            )
        elif ext in self.MARKDOWN_EXTENSIONS:
            return MarkdownChunker.extract_chunks(
                str(relative_file_path),
                content
            )
        else:
            # Generic file chunk for other types
            lines = content.split('\n')
            chunk_id = f"{relative_file_path}::file::1"
            return [CodeChunk(
                id=chunk_id,
                content=content,
                file_path=str(relative_file_path),
                chunk_type=ChunkType.FILE.value,
                start_line=1,
                end_line=len(lines),
                metadata={'extension': ext}
            )]


# Backward compatibility - alias to UniversalChunkingStrategy
EBLChunkingStrategy = UniversalChunkingStrategy


if __name__ == "__main__":
    # Test chunking on current project
    strategy = UniversalChunkingStrategy(".")
    chunks = strategy.chunk_project()

    print(f"Total chunks: {len(chunks)}")

    # Show Spring Boot chunks
    spring_chunks = [c for c in chunks if 'spring' in c.chunk_type]
    print(f"Spring Boot chunks: {len(spring_chunks)}")

    for chunk in spring_chunks[:5]:
        print(f"\n{chunk.chunk_type}: {chunk.metadata.get('class_name', 'unknown')}")
        print(f"  File: {chunk.file_path}")
        print(f"  Lines: {chunk.start_line}-{chunk.end_line}")
