#!/bin/bash
set -e

echo "Starting Ollama server in background..."
ollama serve &
OLLAMA_PID=$!

echo "Waiting for Ollama to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "Ollama is ready!"
        break
    fi
    if ! kill -0 $OLLAMA_PID 2>/dev/null; then
        echo "Ollama server exited unexpectedly"
        exit 1
    fi
    sleep 1
done

echo "Checking for required model: $OLLAMA_MODEL"
if ollama list | grep -q "^$OLLAMA_MODEL"; then
    echo "Model $OLLAMA_MODEL already exists"
else
    echo "Pulling model $OLLAMA_MODEL..."
    ollama pull $OLLAMA_MODEL
fi

echo "Ollama setup complete, keeping server running..."
wait $OLLAMA_PID
