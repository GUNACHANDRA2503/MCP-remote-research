from typing import List, Dict
from mcp.server.fastmcp import FastMCP
from pathlib import Path
import logging
import sys
import os
import uvicorn
from starlette.middleware.cors import CORSMiddleware

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
log_stream = sys.stderr if os.getenv("MCP_TRANSPORT", "stdio") == "stdio" else sys.stdout
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=log_stream,
)

# Reduce noise from verbose libraries in stdio mode
if os.getenv("MCP_TRANSPORT", "stdio") == "stdio":
    logging.getLogger("mcp.server.lowlevel.server").setLevel(logging.WARNING)
    logging.getLogger("mcp.server.fastmcp.resources.resource_manager").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("arxiv").setLevel(logging.WARNING)

mcp = FastMCP("research_server")


@mcp.tool()
def search_papers(topic: str, max_results: int = 5) -> str:
    """
    Search for academic papers on arXiv based on a topic.
    
    Args:
        topic: The search topic (e.g., "machine learning", "quantum computing")
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        JSON string with paper IDs and basic info
    """
    import arxiv
    import json
    import os 

    PAPER_DIR = Path(__file__).resolve().parent / "papers"
    os.makedirs(PAPER_DIR, exist_ok=True)

    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=topic,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
        )
        papers = list(client.results(search))
    except Exception as e:
        logging.error(f"ArXiv API error: {e}")
        return json.dumps({
            "error": f"Failed to search ArXiv: {str(e)}",
            "topic": topic
        })
    
    # Create directory for this topic
    topic_dir = topic.lower().replace(" ", "_") 
    path = os.path.join(PAPER_DIR, topic_dir)
    os.makedirs(path, exist_ok=True)
    
    file_path = os.path.join(path, "papers_info.json")

    # Try to load existing papers info
    try:
        with open(file_path, "r", encoding="utf-8") as json_file:
            papers_info = json.load(json_file)
    except (FileNotFoundError, json.JSONDecodeError):
        papers_info = {}

    paper_summaries = []
    for paper in papers:
        paper_id = paper.get_short_id()
        
        # Store full info
        papers_info[paper_id] = {
            "title": paper.title,
            "authors": [author.name for author in paper.authors],
            "summary": paper.summary,
            'pdf_url': paper.pdf_url,
            'published': str(paper.published.date())
        }
        
        # Return brief summary
        paper_summaries.append({
            "id": paper_id,
            "title": paper.title,
            "authors": [author.name for author in paper.authors][:3],  # First 3 authors
            "published": str(paper.published.date())
        })

    # Save updated papers info
    try:
        with open(file_path, "w", encoding="utf-8") as json_file:
            json.dump(papers_info, json_file, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Failed to save papers: {e}")

    logging.info(f"Found {len(paper_summaries)} papers for topic '{topic}'")
    
    return json.dumps({
        "topic": topic,
        "count": len(paper_summaries),
        "papers": paper_summaries
    }, indent=2)

@mcp.tool()
def extract_info(paper_id: str) -> str:
    """
    Extract detailed information from a specific paper by its arXiv ID.
    
    Args:
        paper_id: The arXiv ID of the paper (e.g., "2103.14030")
    
    Returns:
        JSON string with complete paper details including abstract
    """
    import json
    import os 
    
    PAPER_DIR = Path(__file__).resolve().parent / "papers"
    if not os.path.exists(PAPER_DIR):
        return json.dumps({
            "error": "No papers directory found. Please search for papers first using search_papers."
        })

    # Search all topic directories
    for item in os.listdir(PAPER_DIR):
        topic_path = os.path.join(PAPER_DIR, item)
        if os.path.isdir(topic_path):
            file_path = os.path.join(topic_path, "papers_info.json")
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as json_file:
                        papers_info = json.load(json_file)
                        if paper_id in papers_info:
                            logging.info(f"Found info for paper {paper_id}")
                            return json.dumps(papers_info[paper_id], indent=2, ensure_ascii=False)
                except (FileNotFoundError, json.JSONDecodeError) as e:
                    logging.error(f"Error reading {file_path}: {e}")
                    continue
    
    return json.dumps({
        "error": f"No information found for paper ID: {paper_id}",
        "suggestion": "Make sure to search for papers first using search_papers"
    })

@mcp.resource("papers://folders")
def get_available_folders() -> str:
    """
    Get a list of available paper topic folders.
    
    Returns:
        This resource provides a simple list of all available topic folders.
    """
    import os 
    
    PAPER_DIR = Path(__file__).resolve().parent / "papers"
    if not os.path.exists(PAPER_DIR):
        return []
    
    folders = [name for name in os.listdir(PAPER_DIR) if os.path.isdir(os.path.join(PAPER_DIR, name))]
    logging.info(f"Available folders: {folders}")
    content = "# Available Topics\n\n"
    if folders:
        for folder in folders:
            logging.info(f"- {folder}") 
            content += f"- {folder}\n"
        content += f"\nUse @{folder} to access papers in that topic.\n"
    else:
        logging.info("No folders found.")
        content += "No folders found.\n"
    return content

@mcp.resource("papers://{topic}")
def get_papers_in_topic(topic: str) -> str:
    """
    Get a list of papers in a specific topic folder.
    
    Args:
        topic: The topic folder name (e.g., "machine_learning")
    
    Returns:
        This resource provides a list of papers in the specified topic.
    """
    import os
    import json
    
    PAPER_DIR = Path(__file__).resolve().parent / "papers"
    topic_path = topic.lower().replace(" ", "_")
    file_path = os.path.join(PAPER_DIR,topic_path, "papers_info.json")
    
    if not os.path.exists(file_path):
        return f"No papers found for topic: {topic}. Please ensure the topic exists."
    
    try:
        with open(file_path, "r", encoding="utf-8") as json_file:
            papers_info = json.load(json_file)

        content = f"# Papers in Topic: {topic}\n\n"
        for paper_id, paper_info in papers_info.items():
            title = paper_info.get('title', 'Unknown Title')
            authors = paper_info.get('authors', [])
            published = paper_info.get('published', 'Unknown Date')
            pdf_url = paper_info.get('pdf_url', '#')
            summary = paper_info.get('summary', 'No summary available')

            content += f"## {title}\n"
            content += f"- **Paper ID**: {paper_id}\n"
            content += f"- **Authors**: {', '.join(authors) if authors else 'Unknown'}\n"
            content += f"- **Published**: {published}\n"
            content += f"- **PDF URL**: [{pdf_url}]({pdf_url})\n\n"
            content += f"### Summary\n{summary[:500]}...\n\n"
        return content

    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error reading {file_path}: {e}")
        return f"Error reading papers for topic: {topic}."

@mcp.prompt()
def get_search_prompt(topic:str, num_papers:int = 5) -> str:
    """Generate a prompt to find and discuss academic papers on a specific topic."""
    return f"""Search for {num_papers} academic papers about '{topic}' using the search_papers tool. Follow these instructions:
    1. First, search for papers using search_papers(topic='{topic}', max_results={num_papers})
    2. For each paper found, extract and organize the following information:
       - Paper title
       - Authors
       - Publication date
       - Brief summary of the key findings
       - Main contributions or innovations
       - Methodologies used
       - Relevance to the topic '{topic}'
    
    3. Provide a comprehensive summary that includes:
       - Overview of the current state of research in '{topic}'
       - Common themes and trends across the papers
       - Key research gaps or areas for future investigation
       - Most impactful or influential papers in this area
    
    4. Organize your findings in a clear, structured format with headings and bullet points for easy readability.
    
    Please present both detailed information about each paper and a high-level synthesis of the research landscape in {topic}."""

# Get allowed hosts from environment or use default
# For production on Render, RENDER_EXTERNAL_HOSTNAME is automatically set
allowed_hosts = ["localhost", "127.0.0.1"]
render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if render_hostname:
    allowed_hosts.append(render_hostname)
    logging.info(f"[OK] Added Render hostname to allowed hosts: {render_hostname}")
else:
    logging.warning("[WARN] RENDER_EXTERNAL_HOSTNAME not set - only localhost allowed")

logging.info(f"Allowed hosts: {allowed_hosts}")
logging.info(f"[DEBUG] PORT env: {os.getenv('PORT')}, HOST env: {os.getenv('HOST')}")
logging.info(f"[DEBUG] RENDER_EXTERNAL_HOSTNAME: {os.getenv('RENDER_EXTERNAL_HOSTNAME')}")
logging.info(f"[DEBUG] RENDER_EXTERNAL_URL: {os.getenv('RENDER_EXTERNAL_URL')}")
logging.info(f"[DEBUG] All RENDER_* env vars: {[k for k in os.environ.keys() if k.startswith('RENDER')]}")

# Patch MCP's internal host validation (it blocks even localhost!)
# This is necessary because MCP's transport_security blocks before our middleware
try:
    import mcp.server.transport_security as transport_security
    
    # Store original function if it exists
    if hasattr(transport_security, 'check_host_header'):
        original_check = transport_security.check_host_header
        
        def patched_check_host_header(host: str, allowed: list = None):
            """Always allow - bypass MCP's host validation"""
            return True
        
        transport_security.check_host_header = patched_check_host_header
        logging.info("[OK] Successfully patched MCP host validation")
    else:
        logging.warning("[WARN] MCP host validation function not found - may not need patching")
        # Try to list what's available
        available = [x for x in dir(transport_security) if not x.startswith('_') and 'host' in x.lower()]
        logging.warning(f"   Available host-related items: {available}")

except Exception as e:
    logging.warning(f"[WARN] Could not patch MCP host validation: {e}")
    logging.warning("   Server may reject requests from Render domain")

# Create app - use original without wrapping (wrapping breaks MCP initialization)
logging.info("[INIT] Creating MCP streamable_http_app...")
app = mcp.streamable_http_app()
logging.info("[OK] MCP app created successfully")

# Add CORS middleware to handle browser requests
logging.info("[INIT] Adding CORS middleware...")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
logging.info("[OK] CORS middleware added")

if __name__ == "__main__":
    # Check transport mode - default to stdio for Cursor
    transport_mode = os.getenv("MCP_TRANSPORT", "stdio")
    
    if transport_mode == "http" or os.getenv("RENDER"):
        # HTTP mode for Render/remote deployment
        port = int(os.getenv("PORT", 8001))
        host = os.getenv("HOST", "0.0.0.0")
        
        logging.info("="*60)
        logging.info("[START] MCP Server (HTTP)")
        logging.info(f"   Host: {host}")
        logging.info(f"   Port: {port}")
        logging.info("="*60)
        
        uvicorn.run(app, host=host, port=port)
    else:
        # Stdio mode for Cursor
        logging.info("[START] MCP Server (stdio mode for Cursor)")
        mcp.run()
