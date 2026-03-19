# Contributing to Graph Memory

Thank you for your interest in contributing!

## Development Setup

```bash
# Clone the repository
git clone https://github.com/232252/copaw-graph-memory.git
cd copaw-graph-memory

# Install development dependency (for testing)
pip install numpy pytest

# Run tests
python -m graph_memory.test
```

## Project Structure

```
graph_memory/
├── __init__.py          # Package entry
├── db.py                # SQLite database
├── extractor.py         # Knowledge extraction
├── recaller.py          # Recall and context assembly
├── community.py         # Community detection
├── graph_memory.py      # Main class
├── cli.py               # CLI tools
├── sync.py              # Upstream sync
└── test.py              # Unit tests
```

## Code Style

- Follow PEP 8
- Use type hints where possible
- Write docstrings for public functions

## Testing

```bash
# Run all tests
python -m graph_memory.test

# Run specific test
python -c "from graph_memory.test import test_basic_workflow; test_basic_workflow()"
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`python -m graph_memory.test`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Commit Messages

Please follow Conventional Commits:

- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `test:` for test changes
- `refactor:` for code refactoring

Example: `feat: add vector search support`

## Security

- Do not commit API keys or tokens
- Use environment variables for sensitive data
- Run `grep -rn "[0-9]\{15,\}" .` before committing to check for secrets
