#!/usr/bin/env python3
"""
Advanced AI Agent with CrewAI integration and MCP tool support
Based on Docker's compose-for-agents examples
"""

import os
import json
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class AgentConfig:
    """Enhanced configuration for multi-agent systems"""
    model_url: str = "http://localhost:12434/engines/llama.cpp/v1"
    model_name: str = "ai/gpt-oss-20b"
    mcp_gateway_url: str = "http://localhost:3000"
    reasoning_level: str = "medium"
    max_tokens: int = 2000
    temperature: float = 0.7


class MCPToolManager:
    """Manager for Model Context Protocol tools"""
    
    def __init__(self, gateway_url: str):
        self.gateway_url = gateway_url
        self.available_tools = {}
        self._discover_tools()
    
    def _discover_tools(self):
        """Discover available MCP tools from gateway"""
        try:
            response = requests.get(f"{self.gateway_url}/tools")
            if response.status_code == 200:
                self.available_tools = response.json()
                print(f"✅ Discovered {len(self.available_tools)} MCP tools")
            else:
                print("⚠️ No MCP tools available")
        except Exception as e:
            print(f"❌ Failed to connect to MCP gateway: {e}")
    
    def call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool through the gateway"""
        try:
            payload = {
                "tool": tool_name,
                "parameters": parameters
            }
            response = requests.post(f"{self.gateway_url}/call", json=payload)
            return response.json()
        except Exception as e:
            return {"error": f"Tool call failed: {e}"}
    
    def get_tool_description(self, tool_name: str) -> str:
        """Get description of a specific tool"""
        return self.available_tools.get(tool_name, {}).get("description", "No description available")


class CrewAgent:
    """Individual agent in a crew with specific role and capabilities"""
    
    def __init__(self, role: str, goal: str, backstory: str, tools: List[str] = None):
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.tools = tools or []
        self.conversation_history = []
    
    def get_system_prompt(self) -> str:
        """Generate system prompt based on agent's role and capabilities"""
        tools_desc = f"Available tools: {', '.join(self.tools)}" if self.tools else "No tools available"
        
        return f"""You are a {self.role}.

Goal: {self.goal}

Backstory: {self.backstory}

{tools_desc}

When using tools, respond with JSON in this format:
{{"action": "use_tool", "tool": "tool_name", "parameters": {{"param": "value"}}}}

Otherwise, respond normally to help achieve your goal."""


class MultiAgentSystem:
    """CrewAI-style multi-agent orchestration system"""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.mcp_manager = MCPToolManager(self.config.mcp_gateway_url)
        self.agents = {}
        self.task_results = []
        
    def add_agent(self, name: str, agent: CrewAgent) -> None:
        """Add an agent to the crew"""
        self.agents[name] = agent
        print(f"➕ Added agent: {name} ({agent.role})")
    
    def _make_llm_request(self, messages: List[Dict], agent_name: str = None) -> str:
        """Make request to the LLM model"""
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature
        }
        
        try:
            response = requests.post(
                f"{self.config.model_url}/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Error: {e}"
    
    def execute_agent_task(self, agent_name: str, task: str, context: str = "") -> str:
        """Execute a task with a specific agent"""
        if agent_name not in self.agents:
            return f"Agent {agent_name} not found"
        
        agent = self.agents[agent_name]
        
        # Build context for the agent
        messages = [
            {"role": "system", "content": agent.get_system_prompt()},
        ]
        
        # Add conversation history
        messages.extend(agent.conversation_history[-6:])  # Keep recent context
        
        # Add current task with context
        task_prompt = f"Task: {task}"
        if context:
            task_prompt += f"\n\nContext from previous agents: {context}"
        
        messages.append({"role": "user", "content": task_prompt})
        
        # Get response from LLM
        response = self._make_llm_request(messages, agent_name)
        
        # Check if agent wants to use a tool
        try:
            if response.strip().startswith('{') and 'action' in response:
                action_data = json.loads(response)
                if action_data.get("action") == "use_tool":
                    tool_name = action_data.get("tool")
                    parameters = action_data.get("parameters", {})
                    
                    # Execute tool via MCP
                    tool_result = self.mcp_manager.call_tool(tool_name, parameters)
                    
                    # Get final response incorporating tool result
                    tool_context = f"Tool {tool_name} returned: {tool_result}"
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": f"Tool result: {tool_context}. Please provide your final response."})
                    
                    response = self._make_llm_request(messages, agent_name)
        except json.JSONDecodeError:
            pass  # Not a tool call, continue with normal response
        
        # Update agent's conversation history
        agent.conversation_history.append({"role": "user", "content": task_prompt})
        agent.conversation_history.append({"role": "assistant", "content": response})
        
        return response
    
    def execute_crew_workflow(self, workflow: List[Dict[str, str]]) -> Dict[str, Any]:
        """Execute a multi-agent workflow"""
        results = {}
        context = ""
        
        print(f"\n🚀 Starting crew workflow with {len(workflow)} tasks")
        print("=" * 60)
        
        for i, step in enumerate(workflow, 1):
            agent_name = step["agent"]
            task = step["task"]
            
            print(f"\n📋 Step {i}: {agent_name}")
            print(f"Task: {task}")
            print("-" * 40)
            
            result = self.execute_agent_task(agent_name, task, context)
            results[f"step_{i}_{agent_name}"] = {
                "task": task,
                "result": result,
                "timestamp": datetime.now().isoformat()
            }
            
            print(f"✅ Result: {result[:200]}{'...' if len(result) > 200 else ''}")
            
            # Pass result as context to next agent
            context += f"\n{agent_name} completed: {result}\n"
        
        self.task_results.append({
            "workflow": workflow,
            "results": results,
            "timestamp": datetime.now().isoformat()
        })
        
        return results


def create_research_crew() -> MultiAgentSystem:
    """Create a research-focused multi-agent crew"""
    crew = MultiAgentSystem()
    
    # Add specialized agents
    researcher = CrewAgent(
        role="Senior Research Analyst",
        goal="Conduct thorough research on given topics using available tools",
        backstory="You are an experienced researcher with access to web search and data analysis tools.",
        tools=["web_search", "duckduckgo", "wikipedia"]
    )
    
    analyst = CrewAgent(
        role="Data Analyst", 
        goal="Analyze and synthesize research findings into insights",
        backstory="You specialize in analyzing complex information and extracting key insights.",
        tools=["data_analysis", "statistics"]
    )
    
    writer = CrewAgent(
        role="Technical Writer",
        goal="Create clear, comprehensive reports from research and analysis",
        backstory="You excel at translating complex research into accessible, well-structured content.",
        tools=["document_generation"]
    )
    
    crew.add_agent("researcher", researcher)
    crew.add_agent("analyst", analyst) 
    crew.add_agent("writer", writer)
    
    return crew


def main():
    """Demo the multi-agent system"""
    print("🤖 GPT-OSS-20B Multi-Agent Crew Demo")
    print("Based on Docker compose-for-agents patterns")
    print("=" * 50)
    
    # Create research crew
    crew = create_research_crew()
    
    # Define a research workflow
    research_topic = input("\n📝 Enter research topic: ").strip() or "AI agent development trends"
    
    workflow = [
        {
            "agent": "researcher",
            "task": f"Research the latest developments in {research_topic}. Find key trends, technologies, and industry insights."
        },
        {
            "agent": "analyst", 
            "task": f"Analyze the research findings about {research_topic}. Identify patterns, opportunities, and potential challenges."
        },
        {
            "agent": "writer",
            "task": f"Create a comprehensive report on {research_topic} based on the research and analysis. Include executive summary, key findings, and recommendations."
        }
    ]
    
    # Execute the workflow
    results = crew.execute_crew_workflow(workflow)
    
    # Display final results
    print("\n" + "=" * 60)
    print("📊 FINAL CREW RESULTS")
    print("=" * 60)
    
    for step_key, step_result in results.items():
        print(f"\n🔍 {step_key.upper()}")
        print(f"Task: {step_result['task']}")
        print(f"Result: {step_result['result']}")
        print(f"Completed: {step_result['timestamp']}")
        print("-" * 40)


if __name__ == "__main__":
    main()
