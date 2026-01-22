# MCP Research Server

A Model Context Protocol (MCP) server for searching and managing academic research papers from arXiv.

## Features

- 🔍 **Search Papers**: Search arXiv for academic papers by topic
- 📄 **Extract Info**: Get detailed information about specific papers
- 📂 **Resources**: Browse papers organized by topic folders
- 💡 **Prompts**: Pre-configured prompts for research analysis

## Local Development

### Prerequisites

- Python 3.12+
- uv (recommended) or pip

### Installation

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

### Running the Server

```bash
# Using uv
uv run server/research_server.py

# Or directly
python server/research_server.py
```

The server will start on `http://localhost:8001`

### Testing with MCP Inspector

```bash
npx @modelcontextprotocol/inspector
```

Then connect to: `http://localhost:8001/mcp`

## Deployment to Render

### Quick Deploy

1. Push your code to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com/)
3. Click "New +" → "Web Service"
4. Connect your GitHub repository
5. Render will automatically detect `render.yaml` and configure everything

### Manual Configuration

If not using `render.yaml`:

- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python server/research_server.py`
- **Environment Variables**:
  - `LOG_LEVEL`: `INFO` (optional, defaults to INFO)
  - Render automatically sets `PORT` - no need to configure

### After Deployment

Your MCP server will be available at:
```
https://your-app-name.onrender.com/mcp
```

Use this URL in MCP clients to connect to your deployed server.

## Available Tools

### 1. `search_papers`
Search for academic papers on arXiv.

**Parameters:**
- `topic` (string): Search topic (e.g., "machine learning")
- `max_results` (int): Maximum results to return (default: 5)

### 2. `extract_info`
Get detailed information about a specific paper.

**Parameters:**
- `paper_id` (string): arXiv paper ID (e.g., "2103.14030")

## Available Resources

### `papers://folders`
List all available paper topic folders.

### `papers://{topic}`
Get all papers in a specific topic folder.

## Available Prompts

### `get_search_prompt`
Generate a comprehensive research analysis prompt.

**Parameters:**
- `topic` (string): Research topic
- `num_papers` (int): Number of papers to analyze (default: 5)

## Project Structure

```
MCP_handson/
├── server/
│   ├── research_server.py    # Main MCP server
│   ├── papers/                # Stored paper data (git-ignored)
│   └── __init__.py
├── client/
│   └── mcp_client.py         # Test client
├── requirements.txt          # Python dependencies
├── runtime.txt              # Python version for Render
├── render.yaml              # Render deployment config
├── Procfile                 # Alternative deployment config
└── README.md
```

## Environment Variables

- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR) - default: INFO
- `PORT`: Server port - default: 8001 (Render sets this automatically)
- `HOST`: Server host - default: 0.0.0.0

## Storage

Papers are stored in `server/papers/` directory organized by topic. Each topic folder contains a `papers_info.json` file with paper metadata.

**Note**: On Render's free tier, the filesystem is ephemeral. Papers will need to be re-fetched after deployments.

## License

MIT

## Contributing

Contributions welcome! Please open an issue or submit a pull request.
