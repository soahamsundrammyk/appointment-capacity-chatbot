#!/bin/bash
# Deployment script for Capacity Chatbot Service
# Uses langgraph up for LangSmith persistence
#
# Usage: ./deploy.sh

set -e  # Exit on error

echo "🚀 Capacity Chatbot Service - Deployment Script"
echo "================================================"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "📝 Please create a .env file with your configuration."
    echo "   See .env.example for required variables."
    exit 1
fi

# Check for required environment variables
source .env

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ Error: ANTHROPIC_API_KEY not set in .env"
    exit 1
fi

if [ -z "$LANGSMITH_API_KEY" ]; then
    echo "⚠️  Warning: LANGSMITH_API_KEY not set. LangSmith persistence will not work."
fi

# Check if langgraph CLI is installed
if ! command -v langgraph &> /dev/null; then
    echo "❌ Error: langgraph CLI not installed!"
    echo "📦 Install: pip install 'langgraph-cli[inmem]>=0.4.7'"
    exit 1
fi

echo ""
echo "📦 Starting LangGraph server with persistence..."
echo "   Using: langgraph up"
echo ""

# Start LangGraph with 'up' command for LangSmith persistence
# This enables PostgreSQL checkpointing via LangSmith
langgraph up --host 0.0.0.0 --port "${BACKEND_PORT:-3334}"
