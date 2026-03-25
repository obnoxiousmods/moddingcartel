#!/bin/bash
# This script is used to launch uvicorn with the appropriate settings for development or production.

uv run uvicorn app.main:app --host 0.0.0.0 --port 6069 --reload