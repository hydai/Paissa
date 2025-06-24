# GitHub Actions Workflows

This directory contains CI/CD workflows for the PaissaDB client project.

## Workflows

### 1. Lint (`lint.yml`)
- **Trigger**: Push to master, Pull requests
- **Purpose**: Code quality checks
- **Checks**:
  - Black (code formatting)
  - isort (import sorting)
  - flake8 (linting)
  - mypy (type checking)
- **Python versions**: 3.9, 3.10, 3.11, 3.12

### 2. Docker Build and Push (`docker.yml`)
- **Trigger**: 
  - Push to master
  - Version tags (v*)
  - Pull requests (build only, no push)
  - Manual dispatch
- **Purpose**: Build and publish Docker images
- **Registry**: GitHub Container Registry (ghcr.io)
- **Platforms**: linux/amd64, linux/arm64
- **Features**:
  - Multi-platform builds
  - Automatic tagging (latest, version, sha)
  - Build caching
  - SBOM generation

## Usage

### Running Lints Locally
```bash
pip install -r requirements-dev.txt
black --check .
isort --check-only .
flake8 .
mypy .
```

### Docker Image Tags
- `latest`: Latest master branch build
- `master`: Master branch builds
- `v1.0.0`: Version tags
- `1.0`: Major.minor tags
- `1`: Major version tags
- `master-sha`: SHA-based tags for master

### Pulling Docker Images
```bash
docker pull ghcr.io/hydai/paissa:latest
```