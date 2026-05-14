# Ollama Integration Setup

This guide explains how to integrate Ollama with Llama 3.1 into the GraphRAG Learning Platform to resolve Gemini API issues.

## Prerequisites

- Python 3.8+
- Virtual environment activated
- Backend dependencies installed

## Quick Setup

### 1. Install Ollama

**Windows:**

```bash
# Download and run the installer from: https://ollama.ai/download
# Or use the setup script:
python scripts\setup_ollama.py
```

**Linux:**

```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**macOS:**

```bash
brew install ollama
```

### 2. Start Ollama Service

```bash
# Start Ollama in the background
ollama serve
```

### 3. Pull Llama 3.1 Model

```bash
ollama pull llama3.1
```

### 4. Configure Environment

Create or update your `.env` file:

```env
# Enable Ollama instead of Gemini
USE_OLLAMA=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
OLLAMA_TIMEOUT=120

# Optional: Keep Gemini as fallback
GEMINI_API_KEY=your_gemini_key_here
GEMINI_MODEL=gemini-2.0-flash
```

### 5. Test Integration

```bash
# Test Ollama connection
python scripts\test_ollama.py

# Test full RAG pipeline
python scripts\test_e2e_v3.py
```

## Manual Setup Steps

If the automated script doesn't work:

1. **Install Ollama** from https://ollama.ai

2. **Start the service:**

   ```bash
   ollama serve
   ```

3. **Download the model:**

   ```bash
   ollama pull llama3.1
   ```

4. **Verify installation:**

   ```bash
   curl http://localhost:11434/api/tags
   ```

5. **Update configuration** in `app/core/config.py` or `.env`

## Troubleshooting

### Connection Issues

- Ensure Ollama is running: `ollama serve`
- Check if port 11434 is available
- Verify model is downloaded: `ollama list`

### Model Issues

- Pull the model: `ollama pull llama3.1`
- Check available models: `ollama list`

### Configuration Issues

- Ensure `USE_OLLAMA=true` in your environment
- Check `OLLAMA_BASE_URL` is correct
- Verify model name matches: `llama3.1`

## Architecture Changes

The integration modifies the LLM gateway to:

1. **Primary Path**: Use Ollama when `USE_OLLAMA=true`
2. **Fallback Path**: Use Gemini when Ollama fails or is disabled
3. **Simplified Orchestrator**: Skip tool calling for Ollama (not supported)
4. **Direct Synthesis**: Use simpler prompt-response approach with Ollama

## Performance Notes

- **Ollama + Llama 3.1**: Runs locally, no API costs, slower but private
- **Gemini**: Cloud-based, faster, requires API key and has rate limits
- **Hybrid Mode**: Can configure fallback from Ollama to Gemini

## Running the Application

With Ollama configured:

```bash
# Backend
python -m uvicorn app.api.server:app --reload --host 0.0.0.0 --port 8001

# Frontend (separate terminal)
npm run dev
```

The application will now use Ollama + Llama 3.1 for all LLM operations.
