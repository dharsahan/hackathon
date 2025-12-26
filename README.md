# Smart File Organizer

> 🗂️ An autonomous, privacy-centric intelligent file management system

Smart File Organizer is a Python-based intelligent file management system that automatically organizes your files using local AI classification, cryptographic deduplication, and military-grade encryption. **All processing occurs locally**, ensuring complete data privacy.

## ✨ Features

- **🤖 AI-Powered Classification** - Uses local LLMs (Ollama) for semantic document classification
- **📄 Multi-Tier Classification** - Extension/MIME → Pattern Matching → LLM → Zero-shot fallback
- **🔍 OCR Support** - Extracts text from scanned documents using Tesseract
- **🔐 AES-256 Encryption** - Protects sensitive files with Argon2id key derivation
- **🔄 Smart Deduplication** - Cryptographic + perceptual hashing for exact and similar file detection
- **📁 Automatic Organization** - Moves files to category-based folders with date structuring
- **👁️ Real-time Monitoring** - Watches directories and processes new files automatically
- **🔒 Privacy-First** - Everything runs locally, no cloud dependencies

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) (for OCR functionality)
- [Ollama](https://ollama.ai/) (for AI classification)

### Installation

```bash
# Clone the repository
git clone https://github.com/dharshan/hackathon.git
cd hackathon/smart_file_organizer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Tesseract (Ubuntu/Debian)
sudo apt install tesseract-ocr

# Install Ollama and pull a model
# Visit https://ollama.ai/download
ollama pull llama3
```

### Run the Organizer

```bash
# Run with default configuration
python -m src.main

# Or specify a custom config
python -m src.main --config my_config.yaml
```

## 📖 Configuration

Edit `config.yaml` to customize behavior:

```yaml
watcher:
  watch_directories:
    - ~/Downloads
    - ~/Desktop
  ignore_patterns:
    - "*.tmp"
    - "*.crdownload"
  debounce_seconds: 1.0

classification:
  llm_model: "llama3"
  ocr_enabled: true
  fallback_to_zero_shot: true

security:
  enable_encryption: true
  secure_delete_passes: 3

deduplication:
  enabled: true
  duplicate_action: "quarantine"  # quarantine, delete, skip

organization:
  base_directory: ~/Organized
  use_date_folders: true
```

## 🏗️ Architecture

```
smart_file_organizer/
├── src/
│   ├── config/          # Configuration management
│   │   ├── settings.py  # Dataclass-based config
│   │   └── categories.py # File category definitions
│   │
│   ├── monitoring/      # Filesystem monitoring
│   │   ├── watcher.py   # Watchdog-based file watcher
│   │   └── queue_manager.py # Thread-safe processing queue
│   │
│   ├── extraction/      # Content extraction
│   │   ├── text_extractor.py # PDF, Word, text extraction
│   │   ├── ocr_engine.py     # Tesseract OCR
│   │   └── metadata_reader.py # EXIF, file metadata
│   │
│   ├── classification/  # Multi-tier classification
│   │   ├── tier1_metadata.py  # Extension/MIME
│   │   ├── tier2_content.py   # Pattern matching
│   │   ├── tier3_llm.py       # Ollama LLM
│   │   └── zero_shot.py       # HuggingFace fallback
│   │
│   ├── deduplication/   # Duplicate detection
│   │   ├── hash_engine.py     # SHA-256 hashing
│   │   └── perceptual_hash.py # Image similarity
│   │
│   ├── security/        # Encryption & security
│   │   ├── encryption.py      # AES-256-GCM
│   │   ├── key_derivation.py  # Argon2id KDF
│   │   └── secure_delete.py   # Multi-pass deletion
│   │
│   ├── actions/         # File operations
│   │   ├── file_operations.py # Move, copy, rename
│   │   └── conflict_resolver.py # Duplicate handling
│   │
│   ├── utils/           # Utilities
│   │   ├── logging_config.py # Structured logging
│   │   └── exceptions.py     # Custom exceptions
│   │
│   └── main.py          # Entry point
│
├── tests/               # Test suite
├── config.yaml          # Configuration file
└── requirements.txt     # Dependencies
```

## 📊 Classification Pipeline

```
File → Tier 1 (Extension/MIME) → Tier 2 (Patterns) → Tier 3 (LLM) → Organization
           ↓                          ↓                    ↓
        Fast O(1)               Content Analysis     Semantic Understanding
        
Categories: Documents, Images, Audio, Video, Archives, Installers, Code, Data
```

## 🔒 Security Features

| Feature | Implementation |
|---------|---------------|
| Encryption | AES-256-GCM with authenticated encryption |
| Key Derivation | Argon2id (memory-hard, side-channel resistant) |
| Secure Delete | Multi-pass overwrite (random, zeros, ones) |
| Encrypted Archives | AES-256 ZIP with pyzipper |

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## 📈 Performance

| Operation | Performance |
|-----------|-------------|
| File detection | < 1 second |
| Tier 1 Classification | ~ 1ms |
| LLM Classification | ~ 400ms (Ollama) |
| SHA-256 Hashing | ~ 150 MB/s |
| AES-256 Encryption | ~ 200 MB/s |

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.



---

