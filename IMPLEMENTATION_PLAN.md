# Smart File Organizer - Detailed Implementation Plan

Based on the comprehensive architectural blueprint, this document provides a detailed implementation plan for building the Smart File Organizer system - an autonomous, privacy-centric intelligent file management solution.

---

## 📋 Executive Summary

This implementation plan outlines the development of a Python-based Smart File Organizer that autonomously manages the file lifecycle through:
- **Intelligent Classification** using local LLMs and OCR
- **Storage Optimization** via cryptographic deduplication
- **Data Security** with AES-256 encryption and Argon2id key derivation

All processing occurs locally, ensuring complete data privacy.

---

## 🗂️ Project Structure

```
smart_file_organizer/
├── src/
│   ├── __init__.py
│   ├── main.py                    # Entry point and orchestration
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py            # Configuration management
│   │   └── categories.py          # Category definitions
│   ├── monitoring/
│   │   ├── __init__.py
│   │   ├── watcher.py             # Filesystem event handler
│   │   └── queue_manager.py       # Thread-safe processing queue
│   ├── extraction/
│   │   ├── __init__.py
│   │   ├── text_extractor.py      # PDF, DOCX text extraction
│   │   ├── ocr_engine.py          # Tesseract OCR wrapper
│   │   └── metadata_reader.py     # EXIF, file metadata
│   ├── classification/
│   │   ├── __init__.py
│   │   ├── tier1_metadata.py      # Extension/MIME classification
│   │   ├── tier2_content.py       # Content-based classification
│   │   ├── tier3_llm.py           # Local LLM classification
│   │   └── zero_shot.py           # Fallback transformer classification
│   ├── deduplication/
│   │   ├── __init__.py
│   │   ├── hash_engine.py         # SHA-256, partial hashing
│   │   └── perceptual_hash.py     # Image similarity detection
│   ├── security/
│   │   ├── __init__.py
│   │   ├── encryption.py          # AES-256 encryption
│   │   ├── key_derivation.py      # Argon2id KDF
│   │   └── secure_delete.py       # File shredding
│   ├── actions/
│   │   ├── __init__.py
│   │   ├── file_operations.py     # Move, rename, delete
│   │   └── conflict_resolver.py   # Duplicate handling
│   └── utils/
│       ├── __init__.py
│       ├── logging_config.py      # Structured logging
│       └── exceptions.py          # Custom exceptions
├── tests/
│   ├── __init__.py
│   ├── test_watcher.py
│   ├── test_classification.py
│   ├── test_encryption.py
│   └── test_deduplication.py
├── requirements.txt
├── config.yaml                    # User configuration
└── README.md
```

---

## 📦 Dependencies

```txt
# Core System
watchdog>=4.0.0
pathlib>=1.0.1
pyyaml>=6.0

# Text Extraction
pytesseract>=0.3.10
pdf2image>=1.17.0
PyMuPDF>=1.24.0
python-docx>=1.1.0

# AI/ML Classification
ollama>=0.3.0
transformers>=4.40.0
torch>=2.0.0

# Security
cryptography>=42.0.0
pyzipper>=0.3.6
argon2-cffi>=23.1.0

# Deduplication
ImageHash>=4.3.1

# Utilities
python-magic-bin>=0.4.14
Send2Trash>=1.8.0
Pillow>=10.0.0
opencv-python>=4.9.0
```

---

## 🚀 Implementation Phases

### Phase 1: Core Infrastructure (Week 1-2)

#### 1.1 Configuration Management System

**File: `src/config/settings.py`**

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional
import yaml

@dataclass
class WatcherConfig:
    """Filesystem watcher configuration."""
    watch_directories: List[Path] = field(default_factory=lambda: [
        Path.home() / "Downloads",
        Path.home() / "Desktop"
    ])
    ignore_patterns: List[str] = field(default_factory=lambda: [
        "*.tmp", "*.crdownload", "~$*", ".DS_Store", "Thumbs.db"
    ])
    debounce_seconds: float = 1.0
    recursive: bool = False

@dataclass
class ClassificationConfig:
    """Classification engine configuration."""
    llm_model: str = "llama3"
    llm_backend: str = "ollama"  # "ollama" or "llama-cpp"
    fallback_to_zero_shot: bool = True
    zero_shot_model: str = "facebook/bart-large-mnli"
    max_text_length: int = 2000
    ocr_enabled: bool = True
    ocr_languages: str = "eng"

@dataclass
class SecurityConfig:
    """Security and encryption configuration."""
    enable_encryption: bool = True
    encryption_algorithm: str = "AES-256-GCM"
    key_derivation: str = "argon2id"
    argon2_memory_cost: int = 65536  # 64MB
    argon2_time_cost: int = 3
    argon2_parallelism: int = 4
    secure_delete_passes: int = 3

@dataclass
class DeduplicationConfig:
    """Deduplication settings."""
    enabled: bool = True
    use_partial_hash: bool = True
    partial_hash_size: int = 4096  # 4KB chunks
    perceptual_hash_threshold: int = 5
    duplicate_action: str = "quarantine"  # "quarantine", "delete", "hardlink"

@dataclass
class Config:
    """Main configuration container."""
    watcher: WatcherConfig = field(default_factory=WatcherConfig)
    classification: ClassificationConfig = field(default_factory=ClassificationConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    deduplication: DeduplicationConfig = field(default_factory=DeduplicationConfig)
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """Load configuration from YAML file."""
        if config_path is None:
            config_path = Path("config.yaml")
        if config_path.exists():
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f)
                return cls._from_dict(data)
        return cls()
```

#### 1.2 Deliverables
- [ ] Project scaffolding complete
- [ ] Configuration management system
- [ ] Logging infrastructure
- [ ] Custom exception classes
- [ ] Unit tests for configuration loading

---

### Phase 2: Monitoring Service (Week 2)

#### 2.1 Filesystem Watcher

**File: `src/monitoring/watcher.py`**

```python
import threading
from pathlib import Path
from queue import Queue
from typing import Set
from fnmatch import fnmatch

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, DirCreatedEvent

class DebounceTracker:
    """Tracks file events for debouncing."""
    
    def __init__(self, debounce_seconds: float = 1.0):
        self.debounce_seconds = debounce_seconds
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()
    
    def should_process(self, file_path: str) -> bool:
        """Check if enough time has passed since last event."""
        import time
        current_time = time.time()
        with self._lock:
            last_time = self._pending.get(file_path, 0)
            if current_time - last_time >= self.debounce_seconds:
                self._pending[file_path] = current_time
                return True
            return False

class FileSettlingChecker:
    """Ensures files are fully written before processing."""
    
    @staticmethod
    def is_file_ready(file_path: Path, check_interval: float = 0.5, 
                      max_checks: int = 10) -> bool:
        """Check if file size is stable (file is fully written)."""
        import time
        if not file_path.exists():
            return False
        previous_size = -1
        checks = 0
        while checks < max_checks:
            try:
                current_size = file_path.stat().st_size
                if current_size == previous_size and current_size > 0:
                    with open(file_path, 'rb') as f:
                        f.read(1)
                    return True
                previous_size = current_size
            except (OSError, FileNotFoundError):
                return False
            time.sleep(check_interval)
            checks += 1
        return False

class OrganizerEventHandler(FileSystemEventHandler):
    """Custom event handler for file organization."""
    
    def __init__(self, processing_queue: Queue, config):
        super().__init__()
        self.queue = processing_queue
        self.config = config
        self.debouncer = DebounceTracker(config.debounce_seconds)
        self._processing_set: Set[str] = set()
        self._lock = threading.Lock()
    
    def _should_ignore(self, file_path: str) -> bool:
        """Check if file matches ignore patterns."""
        name = Path(file_path).name
        return any(fnmatch(name, pattern) 
                   for pattern in self.config.ignore_patterns)
    
    def on_created(self, event):
        """Handle file creation events."""
        if isinstance(event, DirCreatedEvent):
            return
        file_path = event.src_path
        if self._should_ignore(file_path):
            return
        if not self.debouncer.should_process(file_path):
            return
        self.queue.put(file_path)

class FileWatcherService:
    """Main watcher service that monitors directories."""
    
    def __init__(self, config, processing_queue: Queue):
        self.config = config
        self.queue = processing_queue
        self.observer = Observer()
        self.handler = OrganizerEventHandler(processing_queue, config)
    
    def start(self):
        """Start watching configured directories."""
        for directory in self.config.watch_directories:
            if directory.exists():
                self.observer.schedule(self.handler, str(directory), recursive=False)
        self.observer.start()
    
    def stop(self):
        """Stop the watcher service."""
        self.observer.stop()
        self.observer.join()
```

#### 2.2 Queue Manager

**File: `src/monitoring/queue_manager.py`**

```python
import threading
from queue import Queue, Empty
from typing import Callable, Optional
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum

class ProcessingStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

@dataclass
class ProcessingTask:
    file_path: str
    status: ProcessingStatus = ProcessingStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3

class ProcessingQueueManager:
    """Manages the file processing queue with worker threads."""
    
    def __init__(self, processor_callback: Callable[[str], bool],
                 max_workers: int = 4, max_retries: int = 3):
        self.queue: Queue[ProcessingTask] = Queue()
        self.processor = processor_callback
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._running = False
    
    def put(self, file_path: str):
        """Add a file to the processing queue."""
        task = ProcessingTask(file_path=file_path, max_retries=self.max_retries)
        self.queue.put(task)
    
    def start(self):
        """Start the queue processing worker."""
        self._running = True
        self._worker_thread = threading.Thread(target=self._process_loop, daemon=True)
        self._worker_thread.start()
    
    def _process_loop(self):
        """Main processing loop."""
        while self._running:
            try:
                task = self.queue.get(timeout=1.0)
                self.executor.submit(self._process_task, task)
            except Empty:
                continue
    
    def _process_task(self, task: ProcessingTask):
        """Process a single task."""
        task.status = ProcessingStatus.PROCESSING
        try:
            success = self.processor(task.file_path)
            if success:
                task.status = ProcessingStatus.COMPLETED
            else:
                self._handle_failure(task, "Processing returned False")
        except Exception as e:
            self._handle_failure(task, str(e))
    
    def _handle_failure(self, task: ProcessingTask, error: str):
        """Handle task failure with retry logic."""
        task.retry_count += 1
        if task.retry_count < task.max_retries:
            task.status = ProcessingStatus.RETRYING
            self.queue.put(task)
        else:
            task.status = ProcessingStatus.FAILED
```

#### 2.3 Deliverables
- [ ] Filesystem watcher with debouncing
- [ ] File settling detection
- [ ] Thread-safe processing queue
- [ ] Worker thread pool management
- [ ] Retry logic for failed operations

---

### Phase 3: Content Extraction (Week 3)

#### 3.1 Text Extractor

**File: `src/extraction/text_extractor.py`**

```python
from pathlib import Path
from typing import Optional, Tuple
from abc import ABC, abstractmethod
import fitz  # PyMuPDF
from docx import Document

class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, file_path: Path) -> Tuple[str, dict]:
        pass
    
    @abstractmethod
    def supports(self, file_path: Path) -> bool:
        pass

class PDFExtractor(BaseExtractor):
    SUPPORTED_EXTENSIONS = {'.pdf'}
    
    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS
    
    def extract(self, file_path: Path) -> Tuple[str, dict]:
        text_parts = []
        doc = fitz.open(file_path)
        metadata = {
            "page_count": doc.page_count,
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
        }
        for page_num, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                text_parts.append(text)
            # Optimization: stop after first few pages
            if page_num >= 2 and len("".join(text_parts)) > 3000:
                break
        doc.close()
        return "\n".join(text_parts), metadata

class WordExtractor(BaseExtractor):
    SUPPORTED_EXTENSIONS = {'.docx', '.doc'}
    
    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS
    
    def extract(self, file_path: Path) -> Tuple[str, dict]:
        doc = Document(file_path)
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        metadata = {
            "paragraph_count": len(doc.paragraphs),
            "title": doc.core_properties.title or "",
        }
        return "\n".join(paragraphs), metadata

class TextExtractionService:
    def __init__(self):
        self.extractors = [PDFExtractor(), WordExtractor()]
    
    def extract(self, file_path: Path) -> Optional[Tuple[str, dict]]:
        for extractor in self.extractors:
            if extractor.supports(file_path):
                return extractor.extract(file_path)
        return None
```

#### 3.2 OCR Engine

**File: `src/extraction/ocr_engine.py`**

```python
from pathlib import Path
from dataclasses import dataclass
import pytesseract
from PIL import Image
import cv2
import numpy as np

@dataclass
class OCRConfig:
    languages: str = "eng"
    dpi: int = 300
    enable_preprocessing: bool = True
    timeout: int = 30

class ImagePreprocessor:
    @staticmethod
    def preprocess(image: np.ndarray) -> np.ndarray:
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        # Apply Gaussian blur
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        # Adaptive thresholding
        binary = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        # Denoise
        denoised = cv2.fastNlMeansDenoising(binary, None, 10, 7, 21)
        return denoised

class OCREngine:
    def __init__(self, config: OCRConfig = None):
        self.config = config or OCRConfig()
        self.preprocessor = ImagePreprocessor()
    
    def extract_text(self, image_path: Path) -> str:
        image = cv2.imread(str(image_path))
        if self.config.enable_preprocessing:
            processed = self.preprocessor.preprocess(image)
        else:
            processed = image
        pil_image = Image.fromarray(processed)
        text = pytesseract.image_to_string(
            pil_image,
            lang=self.config.languages,
            timeout=self.config.timeout,
            config='--psm 1 --oem 3'
        )
        return text.strip()
```

#### 3.3 Deliverables
- [ ] PDF text extraction (PyMuPDF)
- [ ] Word document extraction (python-docx)
- [ ] Plain text file handling
- [ ] OCR engine with Tesseract
- [ ] Image preprocessing pipeline
- [ ] Performance optimizations (partial page scanning)

---

### Phase 4: Classification Engine (Week 4-5)

#### 4.1 Tier 1 - Metadata Classification

**File: `src/classification/tier1_metadata.py`**

```python
from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass
from enum import Enum
import magic
import re

class FileCategory(Enum):
    DOCUMENTS = "Documents"
    IMAGES = "Images"
    AUDIO = "Audio"
    VIDEO = "Video"
    ARCHIVES = "Archives"
    INSTALLERS = "Installers"
    CODE = "Code"
    DATA = "Data"
    UNKNOWN = "Unknown"

@dataclass
class ClassificationResult:
    category: FileCategory
    subcategory: Optional[str] = None
    confidence: float = 1.0
    classification_tier: int = 1
    is_sensitive: bool = False
    metadata: Dict = None

class ExtensionMapper:
    EXTENSION_MAP = {
        '.pdf': (FileCategory.DOCUMENTS, 'PDF'),
        '.docx': (FileCategory.DOCUMENTS, 'Word'),
        '.jpg': (FileCategory.IMAGES, 'Photo'),
        '.png': (FileCategory.IMAGES, 'Image'),
        '.mp3': (FileCategory.AUDIO, 'Music'),
        '.mp4': (FileCategory.VIDEO, 'Video'),
        '.zip': (FileCategory.ARCHIVES, 'Zip'),
        '.exe': (FileCategory.INSTALLERS, 'Windows'),
        '.py': (FileCategory.CODE, 'Python'),
        '.json': (FileCategory.DATA, 'JSON'),
        # ... additional mappings
    }
    
    @classmethod
    def classify(cls, file_path: Path) -> Optional[tuple]:
        ext = file_path.suffix.lower()
        return cls.EXTENSION_MAP.get(ext)

class Tier1Classifier:
    def __init__(self):
        self.extension_mapper = ExtensionMapper()
    
    def classify(self, file_path: Path) -> ClassificationResult:
        ext_result = self.extension_mapper.classify(file_path)
        if ext_result:
            category, subcategory = ext_result
        else:
            category = FileCategory.UNKNOWN
            subcategory = None
        
        # MIME type validation
        try:
            mime = magic.Magic(mime=True)
            mime_type = mime.from_file(str(file_path))
        except:
            mime_type = None
        
        return ClassificationResult(
            category=category,
            subcategory=subcategory,
            metadata={'mime_type': mime_type}
        )
    
    def needs_deeper_analysis(self, result: ClassificationResult) -> bool:
        return result.category in [FileCategory.DOCUMENTS, FileCategory.UNKNOWN]
```

#### 4.2 Tier 3 - LLM Classification

**File: `src/classification/tier3_llm.py`**

```python
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import json
import re
import ollama

@dataclass
class LLMResponse:
    category: str
    subcategory: Optional[str] = None
    summary: Optional[str] = None
    document_date: Optional[str] = None
    is_sensitive: bool = False
    confidence: float = 0.8

class PromptTemplates:
    SYSTEM_PROMPT = """You are an expert file archivist and document classifier.
Your task is to analyze document content and classify it accurately.
Always respond with valid JSON only."""
    
    CLASSIFICATION_PROMPT = """Analyze this document excerpt and classify it.

DOCUMENT TEXT:
\"\"\"
{text}
\"\"\"

CATEGORIES: Finance, Medical, Legal, Personal, Work, Education, Receipts, Insurance, Other

Respond with ONLY this JSON:
{{
    "category": "category_name",
    "subcategory": "specific type",
    "summary": "5 word summary",
    "document_date": "YYYY-MM-DD or null",
    "is_sensitive": true/false,
    "confidence": 0.0-1.0
}}"""

class Tier3LLMClassifier:
    def __init__(self, model: str = "llama3"):
        self.model = model
        self.templates = PromptTemplates()
    
    def is_available(self) -> bool:
        try:
            models = ollama.list()
            return any(self.model in m['name'] for m in models.get('models', []))
        except:
            return False
    
    def classify(self, text: str, max_length: int = 2000) -> Optional[LLMResponse]:
        truncated = text[:max_length]
        prompt = self.templates.CLASSIFICATION_PROMPT.format(text=truncated)
        
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': self.templates.SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt}
                ],
                options={'temperature': 0.1, 'num_predict': 256}
            )
            return self._parse_response(response['message']['content'])
        except Exception as e:
            return None
    
    def _parse_response(self, response_text: str) -> Optional[LLMResponse]:
        json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
        if not json_match:
            return None
        try:
            data = json.loads(json_match.group())
            return LLMResponse(
                category=data.get('category', 'Other'),
                subcategory=data.get('subcategory'),
                summary=data.get('summary'),
                document_date=data.get('document_date'),
                is_sensitive=data.get('is_sensitive', False),
                confidence=float(data.get('confidence', 0.8))
            )
        except json.JSONDecodeError:
            return None
```

#### 4.3 Deliverables
- [ ] Tier 1: Extension/MIME classification
- [ ] Tier 2: Content-based analysis
- [ ] Tier 3: LLM semantic classification
- [ ] Zero-shot fallback classifier
- [ ] Classification result data structures
- [ ] Tiered escalation logic

---

### Phase 5: Deduplication Engine (Week 5)

#### 5.1 Hash Engine

**File: `src/deduplication/hash_engine.py`**

```python
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass
from enum import Enum
import hashlib
import os

class DuplicateStatus(Enum):
    UNIQUE = "unique"
    EXACT_DUPLICATE = "exact_duplicate"
    LIKELY_DUPLICATE = "likely_duplicate"

@dataclass
class HashResult:
    file_path: Path
    file_size: int
    partial_hash: Optional[str] = None
    full_hash: Optional[str] = None
    status: DuplicateStatus = DuplicateStatus.UNIQUE
    duplicate_of: Optional[Path] = None

class PartialHasher:
    """Implements partial hashing for fast comparison."""
    
    def __init__(self, chunk_size: int = 4096):
        self.chunk_size = chunk_size
    
    def compute(self, file_path: Path) -> str:
        file_size = file_path.stat().st_size
        if file_size <= self.chunk_size * 3:
            return self._hash_full(file_path)
        
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            # First chunk
            hasher.update(f.read(self.chunk_size))
            # Middle chunk
            f.seek(file_size // 2)
            hasher.update(f.read(self.chunk_size))
            # Last chunk
            f.seek(-self.chunk_size, os.SEEK_END)
            hasher.update(f.read(self.chunk_size))
        return hasher.hexdigest()
    
    def _hash_full(self, file_path: Path) -> str:
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            hasher.update(f.read())
        return hasher.hexdigest()

class FullHasher:
    BUFFER_SIZE = 65536
    
    def compute(self, file_path: Path) -> str:
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while data := f.read(self.BUFFER_SIZE):
                hasher.update(data)
        return hasher.hexdigest()

class DeduplicationEngine:
    def __init__(self):
        self.partial_hasher = PartialHasher()
        self.full_hasher = FullHasher()
        self._size_index: Dict[int, List[Path]] = {}
        self._hash_index: Dict[str, Path] = {}
    
    def check_duplicate(self, file_path: Path) -> HashResult:
        file_size = file_path.stat().st_size
        result = HashResult(file_path=file_path, file_size=file_size)
        
        # Stage 1: Size comparison
        if file_size not in self._size_index:
            self._size_index[file_size] = [file_path]
            return result
        
        # Stage 2: Partial hash
        partial_hash = self.partial_hasher.compute(file_path)
        result.partial_hash = partial_hash
        
        # Stage 3: Full hash for confirmation
        full_hash = self.full_hasher.compute(file_path)
        result.full_hash = full_hash
        
        if full_hash in self._hash_index:
            result.status = DuplicateStatus.EXACT_DUPLICATE
            result.duplicate_of = self._hash_index[full_hash]
        else:
            self._hash_index[full_hash] = file_path
            self._size_index[file_size].append(file_path)
        
        return result
```

#### 5.2 Perceptual Hashing

**File: `src/deduplication/perceptual_hash.py`**

```python
from pathlib import Path
from typing import Optional, List, Tuple
from dataclasses import dataclass
import imagehash
from PIL import Image

@dataclass
class PerceptualHashResult:
    file_path: Path
    hash_value: str
    similar_files: List[Tuple[Path, int]] = None  # (path, distance)

class PerceptualHashEngine:
    def __init__(self, threshold: int = 5):
        self.threshold = threshold
        self._hash_index: dict = {}
    
    def compute_hash(self, image_path: Path) -> str:
        img = Image.open(image_path)
        return str(imagehash.phash(img))
    
    def find_similar(self, image_path: Path) -> PerceptualHashResult:
        current_hash = imagehash.hex_to_hash(self.compute_hash(image_path))
        similar = []
        
        for stored_path, stored_hash_str in self._hash_index.items():
            stored_hash = imagehash.hex_to_hash(stored_hash_str)
            distance = current_hash - stored_hash
            if distance <= self.threshold:
                similar.append((stored_path, distance))
        
        # Add to index
        self._hash_index[image_path] = str(current_hash)
        
        return PerceptualHashResult(
            file_path=image_path,
            hash_value=str(current_hash),
            similar_files=similar
        )
```

#### 5.3 Deliverables
- [ ] SHA-256 full file hashing
- [ ] Partial hashing optimization
- [ ] Perceptual hashing for images
- [ ] Hash database/index
- [ ] Duplicate detection pipeline
- [ ] Conflict resolution strategies

---

### Phase 6: Security Module (Week 6)

#### 6.1 Key Derivation

**File: `src/security/key_derivation.py`**

```python
import os
import secrets
from dataclasses import dataclass
from argon2 import PasswordHasher
from argon2.low_level import hash_secret_raw, Type

@dataclass
class DerivedKey:
    key: bytes
    salt: bytes
    
class KeyDerivationService:
    def __init__(self, memory_cost: int = 65536, time_cost: int = 3, 
                 parallelism: int = 4):
        self.memory_cost = memory_cost
        self.time_cost = time_cost
        self.parallelism = parallelism
    
    def derive_key(self, password: str, salt: bytes = None) -> DerivedKey:
        if salt is None:
            salt = secrets.token_bytes(16)
        
        key = hash_secret_raw(
            secret=password.encode('utf-8'),
            salt=salt,
            time_cost=self.time_cost,
            memory_cost=self.memory_cost,
            parallelism=self.parallelism,
            hash_len=32,  # 256 bits for AES-256
            type=Type.ID  # Argon2id
        )
        return DerivedKey(key=key, salt=salt)
```

#### 6.2 AES-256 Encryption

**File: `src/security/encryption.py`**

```python
from pathlib import Path
import os
import pyzipper
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class AESEncryptor:
    def __init__(self):
        self.nonce_size = 12
    
    def encrypt_bytes(self, data: bytes, key: bytes) -> bytes:
        nonce = os.urandom(self.nonce_size)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext
    
    def decrypt_bytes(self, encrypted: bytes, key: bytes) -> bytes:
        nonce = encrypted[:self.nonce_size]
        ciphertext = encrypted[self.nonce_size:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None)

class SecureArchiver:
    """Create AES-256 encrypted ZIP archives."""
    
    def create_archive(self, file_path: Path, password: str) -> Path:
        dest_zip = file_path.with_suffix('.zip')
        
        with pyzipper.AESZipFile(dest_zip, 'w', 
                                  compression=pyzipper.ZIP_LZMA,
                                  encryption=pyzipper.WZ_AES) as zf:
            zf.setpassword(password.encode('utf-8'))
            zf.setencryption(pyzipper.WZ_AES, nbits=256)
            zf.write(file_path, arcname=file_path.name)
        
        return dest_zip
    
    def extract_archive(self, archive_path: Path, password: str, 
                        dest_dir: Path) -> List[Path]:
        extracted = []
        with pyzipper.AESZipFile(archive_path, 'r') as zf:
            zf.setpassword(password.encode('utf-8'))
            zf.extractall(dest_dir)
            extracted = [dest_dir / name for name in zf.namelist()]
        return extracted
```

#### 6.3 Secure Deletion

**File: `src/security/secure_delete.py`**

```python
from pathlib import Path
import os
import secrets

class SecureDeleter:
    def __init__(self, passes: int = 3):
        self.passes = passes
    
    def secure_delete(self, file_path: Path) -> bool:
        if not file_path.exists():
            return False
        
        file_size = file_path.stat().st_size
        
        try:
            with open(file_path, 'r+b') as f:
                for _ in range(self.passes):
                    f.seek(0)
                    f.write(secrets.token_bytes(file_size))
                    f.flush()
                    os.fsync(f.fileno())
            
            # Finally delete the file
            file_path.unlink()
            return True
        except Exception:
            return False
```

#### 6.4 Deliverables
- [ ] Argon2id key derivation
- [ ] AES-256-GCM encryption
- [ ] Encrypted ZIP archive creation
- [ ] Archive extraction with decryption
- [ ] Secure file deletion (multi-pass overwrite)
- [ ] Key/salt management

---

### Phase 7: Integration & Main Application (Week 7)

#### 7.1 Main Orchestrator

**File: `src/main.py`**

```python
import signal
import sys
from queue import Queue
from pathlib import Path

from src.config.settings import Config
from src.monitoring.watcher import FileWatcherService
from src.monitoring.queue_manager import ProcessingQueueManager
from src.extraction.text_extractor import TextExtractionService
from src.extraction.ocr_engine import OCREngine
from src.classification.tier1_metadata import Tier1Classifier
from src.classification.tier3_llm import Tier3LLMClassifier
from src.deduplication.hash_engine import DeduplicationEngine
from src.security.encryption import SecureArchiver
from src.security.key_derivation import KeyDerivationService

class SmartFileOrganizer:
    def __init__(self, config_path: Path = None):
        self.config = Config.load(config_path)
        self.processing_queue = Queue()
        
        # Initialize components
        self.watcher = FileWatcherService(
            self.config.watcher, 
            self.processing_queue
        )
        self.queue_manager = ProcessingQueueManager(
            processor_callback=self.process_file,
            max_workers=4
        )
        self.text_extractor = TextExtractionService()
        self.ocr_engine = OCREngine()
        self.tier1_classifier = Tier1Classifier()
        self.tier3_classifier = Tier3LLMClassifier()
        self.dedup_engine = DeduplicationEngine()
        self.archiver = SecureArchiver()
        self.key_service = KeyDerivationService()
    
    def process_file(self, file_path: str) -> bool:
        path = Path(file_path)
        
        # Step 1: Check for duplicates
        hash_result = self.dedup_engine.check_duplicate(path)
        if hash_result.status.value != "unique":
            self._handle_duplicate(path, hash_result)
            return True
        
        # Step 2: Tier 1 classification
        result = self.tier1_classifier.classify(path)
        
        # Step 3: Deep analysis if needed
        if self.tier1_classifier.needs_deeper_analysis(result):
            text_result = self.text_extractor.extract(path)
            if text_result:
                text, metadata = text_result
                llm_result = self.tier3_classifier.classify(text)
                if llm_result:
                    result.subcategory = f"{llm_result.category}/{llm_result.subcategory}"
                    result.is_sensitive = llm_result.is_sensitive
        
        # Step 4: Handle sensitive files
        if result.is_sensitive and self.config.security.enable_encryption:
            self._encrypt_and_vault(path)
            return True
        
        # Step 5: Move to destination
        dest = self._get_destination(result)
        self._move_file(path, dest)
        return True
    
    def _get_destination(self, result) -> Path:
        base = self.config.organization.base_directory
        category_dir = base / result.category.value
        if result.subcategory:
            category_dir = category_dir / result.subcategory
        category_dir.mkdir(parents=True, exist_ok=True)
        return category_dir
    
    def _move_file(self, source: Path, dest_dir: Path):
        import shutil
        dest = dest_dir / source.name
        counter = 1
        while dest.exists():
            dest = dest_dir / f"{source.stem}_{counter}{source.suffix}"
            counter += 1
        shutil.move(str(source), str(dest))
    
    def _handle_duplicate(self, path: Path, result):
        # Implement based on config: quarantine, delete, or skip
        pass
    
    def _encrypt_and_vault(self, path: Path):
        vault_dir = self.config.organization.base_directory / "Vault"
        vault_dir.mkdir(exist_ok=True)
        # Encryption logic here
        pass
    
    def start(self):
        print("Starting Smart File Organizer...")
        self.watcher.start()
        self.queue_manager.start()
        print("Watching directories:", self.config.watcher.watch_directories)
    
    def stop(self):
        print("Stopping Smart File Organizer...")
        self.watcher.stop()
        self.queue_manager.stop()

def main():
    organizer = SmartFileOrganizer()
    
    def signal_handler(sig, frame):
        organizer.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    organizer.start()
    
    # Keep main thread alive
    signal.pause()

if __name__ == "__main__":
    main()
```

#### 7.2 Deliverables
- [ ] Main orchestrator class
- [ ] Component initialization
- [ ] File processing pipeline
- [ ] Signal handling for graceful shutdown
- [ ] CLI interface

---

### Phase 8: Testing & Documentation (Week 8)

#### 8.1 Test Coverage

| Module | Test File | Coverage Target |
|--------|-----------|-----------------|
| Watcher | `test_watcher.py` | 90% |
| Classification | `test_classification.py` | 85% |
| Encryption | `test_encryption.py` | 95% |
| Deduplication | `test_deduplication.py` | 90% |
| Integration | `test_integration.py` | 80% |

#### 8.2 Deliverables
- [ ] Unit tests for all modules
- [ ] Integration tests
- [ ] Performance benchmarks
- [ ] User documentation
- [ ] API documentation
- [ ] Installation guide

---

## 📊 Performance Benchmarks

| Operation | Hardware | Performance | Use Case |
|-----------|----------|-------------|----------|
| LLM Classification (Ollama) | M1 Pro | ~0.4s/file | Interactive |
| LLM Classification (llama.cpp) | M1 Pro | ~0.2s/file | Batch Processing |
| SHA-256 Hashing | Any | ~150 MB/s | All files |
| OCR Processing | CPU | ~2-5s/page | Scanned documents |
| Encryption (AES-256) | Any | ~200 MB/s | Sensitive files |

---

## 🔒 Security Considerations

1. **Local-First**: All processing occurs on-device
2. **Encryption**: AES-256-GCM with Argon2id key derivation
3. **Secure Deletion**: Multi-pass overwrite before file removal
4. **No Cloud Dependencies**: Zero data transmitted externally

---

## 🎯 Success Criteria

- [ ] Real-time file monitoring with < 1s detection latency
- [ ] 95%+ classification accuracy on test dataset
- [ ] Successful encryption/decryption of all file types
- [ ] Zero false positives in duplicate detection
- [ ] < 5% CPU usage in idle monitoring mode
- [ ] Complete test coverage (> 85%)

---

## 📅 Timeline Summary

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1-2 | Core Infrastructure | Project setup, configuration, logging |
| 2 | Monitoring Service | Watcher, queue manager |
| 3 | Content Extraction | Text extraction, OCR |
| 4-5 | Classification | Tier 1-3 classifiers |
| 5 | Deduplication | Hash engine, perceptual hashing |
| 6 | Security | Encryption, key derivation, secure delete |
| 7 | Integration | Main application, CLI |
| 8 | Testing & Docs | Full test suite, documentation |

---

## 🚀 Getting Started

```bash
# Clone repository
git clone https://github.com/dharsahan/hackathon.git
cd hackathon

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Install Tesseract OCR (system dependency)
# macOS: brew install tesseract
# Ubuntu: sudo apt install tesseract-ocr
# Windows: Download from GitHub releases

# Install Ollama for local LLM
# https://ollama.ai/download

# Pull LLM model
ollama pull llama3

# Run the application
python -m src.main
```

---

*This implementation plan provides a comprehensive roadmap for building a production-grade Smart File Organizer with local AI capabilities and military-grade security.*
