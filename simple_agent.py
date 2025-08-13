#!/usr/bin/env python3
"""
Simple AI Agent using OpenAI's GPT-OSS-20B with Docker Model Runner
Author: Ajeet Singh Raina
"""

import os
import json
import requests
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class AgentConfig:
    """Configuration for the AI Agent"""
    model_url: str = "http://localhost:12434/engines/llama.cpp/v1"
    model_name: str = "ai/gpt-oss"
    max_tokens: int = 1000
    temperature: float = 0.7
    reasoning_level: str = "medium"  # low, medium, high


class GPTOSSAgent:
    """Simple AI Agent powered by GPT-OSS-20B via Docker Model Runner"""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.conversation_history = []
        
    def _make_request(self, messages: list) -> Dict[str, Any]:
        """Make a request to the local GPT-OSS-20B model"""
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": False
        }
        
        try:
            response = requests.post(
                f"{self.config.model_url}/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Error communicating with model: {e}")
    
    def chat(self, user_input: str, system_prompt: Optional[str] = None) -> str:
        """Chat with the AI agent"""
        messages = []
        
        # Add system prompt with reasoning level
        if system_prompt:
            messages.append({
                "role": "system", 
                "content": f"{system_prompt}\nReasoning: {self.config.reasoning_level}"
            })
        else:
            messages.append({
                "role": "system",
                "content": f"You are a helpful AI assistant. Reasoning: {self.config.reasoning_level}"
            })
        
        # Add conversation history
        messages.extend(self.conversation_history)
        
        # Add current user input
        messages.append({"role": "user", "content": user_input})
        
        # Get response from model
        response = self._make_request(messages)
        assistant_response = response["choices"][0]["message"]["content"]
        
        # Update conversation history
        self.conversation_history.append({"role": "user", "content": user_input})
        self.conversation_history.append({"role": "assistant", "content": assistant_response})
        
        # Keep conversation history manageable
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
        
        return assistant_response
    
    def think(self, task: str, reasoning_level: str = "high") -> str:
        """Use high reasoning for complex tasks"""
        original_level = self.config.reasoning_level
        self.config.reasoning_level = reasoning_level
        
        system_prompt = """You are an expert problem solver. Break down complex tasks into steps, 
        analyze each component carefully, and provide detailed reasoning for your approach."""
        
        try:
            result = self.chat(task, system_prompt)
            return result
        finally:
            self.config.reasoning_level = original_level
    
    def reset_conversation(self):
        """Reset the conversation history"""
        self.conversation_history = []


def check_docker_model_runner():
    """Check if Docker Model Runner is available and model is running"""
    try:
        config = AgentConfig()
        response = requests.get(f"{config.model_url}/models", timeout=10)
        if response.status_code == 200:
            print("✅ Docker Model Runner is running")
            models = response.json().get("data", [])
            if any(model.get("id") == config.model_name for model in models):
                print(f"✅ Model {config.model_name} is available")
                return True
            else:
                print(f"❌ Model {config.model_name} not found. Run: docker model pull {config.model_name}")
                return False
        else:
            print("❌ Docker Model Runner not responding")
            return False
    except Exception as e:
        print(f"❌ Error checking Docker Model Runner: {e}")
        print("Make sure Docker Model Runner is enabled and the model is pulled")
        return False


def main():
    """Demo the AI Agent"""
    print("🤖 GPT-OSS-20B AI Agent Demo")
    print("=" * 40)
    
    # Check if everything is set up
    if not check_docker_model_runner():
        print("\n📋 Setup Instructions:")
        print("1. Enable Docker Model Runner in Docker Desktop")
        print("2. Run: docker model pull ai/gpt-oss")
        print("3. Wait for the model to download (may take a while)")
        return
    
    # Initialize the agent
    agent = GPTOSSAgent()
    
    print("\n🚀 Agent initialized successfully!")
    print("Type 'quit' to exit, 'reset' to clear conversation, or 'think' for complex reasoning")
    print("-" * 60)
    
    while True:
        try:
            user_input = input("\n👤 You: ").strip()
            
            if user_input.lower() == 'quit':
                print("👋 Goodbye!")
                break
            elif user_input.lower() == 'reset':
                agent.reset_conversation()
                print("🔄 Conversation reset!")
                continue
            elif user_input.lower().startswith('think '):
                task = user_input[6:]  # Remove 'think ' prefix
                print("\n🧠 Agent (thinking deeply):", end=" ")
                response = agent.think(task)
            else:
                print("\n🤖 Agent:", end=" ")
                response = agent.chat(user_input)
            
            print(response)
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
