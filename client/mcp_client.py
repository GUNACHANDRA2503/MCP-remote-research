from dotenv import load_dotenv
from pathlib import Path
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import List, Dict, TypedDict
from contextlib import AsyncExitStack
import asyncio
from openai import OpenAI
import json
import sys

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

class ToolDefinition(TypedDict):
    name: str
    description: str
    input_schema: dict

class MinimalOpenAIMCPBot:
    """
    Minimal OpenAI MCP bot - NO system prompt!
    Supports tools, prompts, and resources from multiple servers.
    """
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()
        self.client = OpenAI()  # API key from env
        
        self.all_tools: List[ToolDefinition] = []
        self.all_prompts: List[dict] = []
        self.all_resources: List[dict] = []
        
        self.tool_to_server: Dict[str, str] = {}
        self.prompt_to_server: Dict[str, str] = {}
        self.resource_to_server: Dict[str, str] = {}  # FIX: Must be initialized here!
        
        self.max_iterations = 15
    
    async def process_query(self, query: str):
        """Process query - GPT decides tool usage automatically"""
        
        messages = [{"role": "user", "content": query}]
        
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            
            # Call OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=self.all_tools,
                tool_choice="auto",
                max_tokens=2048,
                temperature=0.7
            )
            
            message = response.choices[0].message
            
            # Check if GPT wants to use tools
            if message.tool_calls:
                print(f"\n🔧 Tool calls: {[call.function.name for call in message.tool_calls]}")
                
                # Add assistant's response with tool calls
                messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments
                            }
                        }
                        for call in message.tool_calls
                    ]
                })
                
                # Execute each tool call
                for call in message.tool_calls:
                    tool_name = call.function.name
                    tool_args = json.loads(call.function.arguments)
                    tool_id = call.id
                    
                    server_name = self.tool_to_server.get(tool_name, "unknown")
                    print(f"  → [{server_name}] {tool_name}({list(tool_args.keys())})")
                    
                    # Get the right session
                    session = self.sessions.get(server_name)
                    if not session:
                        result = f"Error: Server '{server_name}' not connected"
                        print(f"    ❌ {result}")
                    else:
                        try:
                            mcp_result = await session.call_tool(
                                tool_name,
                                arguments=tool_args
                            )
                            result = mcp_result.content[0].text if mcp_result.content else "No result"
                            print(f"    ✓ Success ({len(result)} chars)")
                        except Exception as e:
                            result = f"Error: {str(e)}"
                            print(f"    ❌ {result[:100]}")
                    
                    # Add tool result to conversation
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": result
                    })
            
            else:
                # No tool calls - this is the final answer
                if message.content:
                    print(f"\n{message.content}")
                return
            
            # Safety check
            if iteration >= self.max_iterations:
                print("\n⚠️ Max iterations reached")
                return
    
    async def chat_loop(self):
        """Interactive chat loop"""
        print("\n" + "="*60)
        print("🤖 Minimal OpenAI MCP Assistant")
        print("="*60)
        print(f"Model: gpt-4o-mini")
        print(f"Servers: {', '.join(self.sessions.keys())}")
        print(f"Tools: {len(self.all_tools)}")
        print(f"Prompts: {len(self.all_prompts)}")
        print(f"Resources: {len(self.all_resources)}")
        print("\nCommands:")
        print("  • Type query to process")
        print("  • 'tools' - Show all tools")
        print("  • 'prompts' - Show all prompts")
        print("  • 'resources' - Show all resources")
        print("  • 'quit' - Exit\n")
        
        while True:
            try:
                query = input("💬 > ").strip()
                
                if query.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye! 👋")
                    return
                
                if not query:
                    continue
                
                if query.lower() == 'tools':
                    self._show_tools()
                    continue
                
                if query.lower() == 'prompts':
                    self._show_prompts()
                    continue
                
                if query.lower() == 'resources':
                    self._show_resources()
                    continue
                
                await self.process_query(query)
                print()  # Blank line after response
                    
            except KeyboardInterrupt:
                print("\n\nType 'quit' to exit.")
                continue
            except EOFError:
                print("\nGoodbye! 👋")
                return
            except Exception as e:
                print(f"\n❌ Error: {str(e)}")
    
    def _show_tools(self):
        """Display all available tools"""
        print("\n📋 Available Tools:")
        by_server = {}
        for tool_name, server_name in self.tool_to_server.items():
            if server_name not in by_server:
                by_server[server_name] = []
            by_server[server_name].append(tool_name)
        
        for server, tools in by_server.items():
            print(f"\n  [{server}] ({len(tools)} tools)")
            for tool in tools:
                print(f"    • {tool}")
    
    def _show_prompts(self):
        """Display all available prompts"""
        if not self.all_prompts:
            print("\n⚠️  No prompts available")
            return
        
        print("\n📝 Available Prompts:")
        by_server = {}
        for prompt_name, server_name in self.prompt_to_server.items():
            if server_name not in by_server:
                by_server[server_name] = []
            by_server[server_name].append(prompt_name)
        
        for server, prompts in by_server.items():
            print(f"\n  [{server}] ({len(prompts)} prompts)")
            for prompt in prompts:
                print(f"    • {prompt}")
    
    def _show_resources(self):
        """Display all available resources"""
        if not self.all_resources:
            print("\n⚠️  No resources available")
            return
        
        print("\n📦 Available Resources:")
        by_server = {}
        for resource in self.all_resources:
            server = resource['server']
            if server not in by_server:
                by_server[server] = []
            by_server[server].append(resource)
        
        for server, resources in by_server.items():
            print(f"\n  [{server}] ({len(resources)} resources)")
            for res in resources:
                print(f"    • {res['name']} - {res['uri']}")
                if res.get('description'):
                    print(f"      {res['description']}")
    
    async def connect_to_server(self, server_name: str, server_params: dict):
        """Connect to a single MCP server and register its capabilities"""
        try:
            # Create stdio parameters
            stdio_params = StdioServerParameters(**server_params)
            
            # Connect via stdio
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(stdio_params)
            )
            read, write = stdio_transport
            
            # Create session
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            
            # Store session
            self.sessions[server_name] = session
            
            print(f"✓ Connected to '{server_name}'")
            
            # === Register tools (ONCE, not in a loop) ===
            try:
                response = await session.list_tools()
                if response and response.tools:
                    tool_names = []
                    for tool in response.tools:
                        # Register tool mapping
                        self.tool_to_server[tool.name] = server_name
                        tool_names.append(tool.name)
                        
                        # Add to all_tools list
                        self.all_tools.append({
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": tool.inputSchema
                            }
                        })
                    
                    # Print ONCE after loop
                    print(f"  📋 Tools: {len(tool_names)} - {tool_names}")
                else:
                    print(f"  📋 Tools: 0")
            except Exception as e:
                # Some servers might not support tools
                print(f"  ⚠️  Tools not available: {e}")
            
            # === Register prompts ===
            try:
                prompt_response = await session.list_prompts()
                if prompt_response and prompt_response.prompts:
                    prompt_names = []
                    for prompt in prompt_response.prompts:
                        # Register prompt mapping
                        self.prompt_to_server[prompt.name] = server_name
                        prompt_names.append(prompt.name)
                        
                        # Add to all_prompts list
                        self.all_prompts.append({
                            "name": prompt.name,
                            "description": prompt.description if hasattr(prompt, 'description') else "",
                            "arguments": prompt.arguments if hasattr(prompt, 'arguments') else []
                        })
                    
                    # Print ONCE after loop
                    print(f"  📝 Prompts: {len(prompt_names)} - {prompt_names}")
                else:
                    print(f"  📝 Prompts: 0")
            except AttributeError as e:
                # Method exists but has wrong variable name
                print(f"  ⚠️  Prompts error: {e}")
            except Exception as e:
                # Server doesn't support prompts
                if "not found" in str(e).lower():
                    print(f"  📝 Prompts: Not supported")
                else:
                    print(f"  ⚠️  Prompts error: {e}")
            
            # === Register resources ===
            try:
                resource_response = await session.list_resources()
                if resource_response and resource_response.resources:
                    resource_names = []
                    for resource in resource_response.resources:
                        resource_name = getattr(resource, 'name', str(resource.uri))
                        resource_names.append(resource_name)
                        
                        # Add to all_resources list
                        self.all_resources.append({
                            "uri": str(resource.uri),
                            "name": resource_name,
                            "description": getattr(resource, 'description', ''),
                            "server": server_name
                        })
                        
                        # Map resource to server
                        self.resource_to_server[resource_name] = server_name
                    
                    # Print ONCE after loop
                    print(f"  📦 Resources: {len(resource_names)} - {resource_names}")
                else:
                    print(f"  📦 Resources: 0")
            except Exception as e:
                # Server doesn't support resources
                if "not found" in str(e).lower():
                    print(f"  📦 Resources: Not supported")
                else:
                    print(f"  ⚠️  Resources error: {e}")
            
        except Exception as e:
            print(f"❌ Failed to connect to '{server_name}': {e}")
            import traceback
            traceback.print_exc()
    
    async def connect_to_servers(self):
        """Connect to all MCP servers from config file"""
        try:
            config_path = Path(__file__).resolve().parents[1] / "servers_config.json"
            
            if not config_path.exists():
                print(f"❌ Config file not found: {config_path}")
                raise FileNotFoundError(f"Config file not found: {config_path}")
            
            with open(config_path, "r", encoding="utf-8") as file:
                servers_config = json.load(file)
            
            print("📡 Connecting to servers...\n")
            
            servers = servers_config.get("mcpServers", {})
            if not servers:
                print("⚠️  No servers found in config")
                return
            
            print(f"Found {len(servers)} server(s) in config\n")
            
            # Connect to each server
            for server_name, server_params in servers.items():
                print(f"🔌 Connecting to '{server_name}'...")
                await self.connect_to_server(server_name, server_params)
                print()  # Blank line between servers
            
            if not self.sessions:
                raise Exception("No servers connected successfully!")
            
            print("="*60)
            print(f"✅ Connected to {len(self.sessions)} server(s)")
            print(f"📋 Total tools: {len(self.all_tools)}")
            print(f"📝 Total prompts: {len(self.all_prompts)}")
            print(f"📦 Total resources: {len(self.all_resources)}")
            print("="*60)
            
        except FileNotFoundError as e:
            print(f"❌ {e}")
            raise
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in config file: {e}")
            raise
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            raise
    
    async def cleanup(self):
        """Cleanly close all resources using AsyncExitStack"""
        print("\n🧹 Cleaning up connections...")
        await self.exit_stack.aclose()
        print("✓ All connections closed")

async def main():
    bot = MinimalOpenAIMCPBot()
    
    try:
        await bot.connect_to_servers()
        await bot.chat_loop()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await bot.cleanup()

if __name__ == "__main__":
    asyncio.run(main())