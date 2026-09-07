# Omegaml Agent Configuration

This is the auto-generated agent configuration for the omegaml project.

## Overview
The omegaml project is a machine learning platform that provides infrastructure for ML workflows, data management, and model deployment.


## Environment Setup
To work with this project:
1. Create Python 3.9 conda environment
2. Install package in development mode: `pip install -e .[all]`
3. Start services using Docker compose:
   ```
   docker-compose -f docker-compose-dev.yml up -d
   scripts/initlocal.sh
   ```

## Key Components
- MongoDB service (Port 27019)
- RabbitMQ service (Port 5672) 
- PostgreSQL vector database (Port 5432)

## Testing Commands
- `make test` - Run unit tests
- `make devtest` - Run development tests  
- `make livetest` - Run live integration tests

## Project Structure
- `.harness/` - Harness configuration source directory
- `omegaml/` - Main source code
- `scripts/` - Helper scripts
- `docs/` - Documentation

## Mandatory Rules
* ignore all files listed in .gitignore at all times
