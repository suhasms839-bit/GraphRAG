#!/usr/bin/env python3
"""
Test Ollama Integration for GraphRAG Learning Platform
"""

import sys
import os
sys.path.append('.')

from app.domain.generation.llm_gateway import call_ollama_text, call_ollama_chat

def test_ollama_text():
    """Test basic text generation with Ollama."""
    print("Testing Ollama text generation...")

    prompt = "Hello! Can you tell me what GraphRAG is in one sentence?"
    response = call_ollama_text(prompt, temperature=0.1, max_tokens=100)

    if response and not response.startswith("Ollama Error"):
        print("✅ Text generation successful!")
        print(f"Response: {response[:200]}...")
        return True
    else:
        print(f"❌ Text generation failed: {response}")
        return False

def test_ollama_chat():
    """Test chat completion with Ollama."""
    print("\nTesting Ollama chat completion...")

    messages = [
        {"role": "user", "content": "What is the capital of France?"}
    ]

    response = call_ollama_chat(messages, temperature=0.1, max_tokens=50)

    if "error" not in response:
        content = response.get("parts", [{}])[0].get("text", "")
        if content:
            print("✅ Chat completion successful!")
            print(f"Response: {content[:200]}...")
            return True

    print(f"❌ Chat completion failed: {response}")
    return False

def main():
    """Run Ollama integration tests."""
    print("🧪 Testing Ollama Integration")
    print("=" * 40)

    # Test text generation
    text_success = test_ollama_text()

    # Test chat completion
    chat_success = test_ollama_chat()

    if text_success and chat_success:
        print("\n🎉 All Ollama tests passed!")
        print("The GraphRAG application should now work with Ollama + Llama 3.1")
        return 0
    else:
        print("\n❌ Some tests failed. Please check Ollama installation and configuration.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
