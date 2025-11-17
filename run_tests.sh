#!/bin/bash
# Test script wrapper for Finance RAG API

# Set API URL (default: localhost:8000)
API_URL="${API_URL:-http://localhost:8000}"

echo "🚀 Starting API tests..."
echo "📍 API URL: $API_URL"
echo ""

# Run the test script
python3 test_api.py

