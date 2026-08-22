# MA-CLI Installation Guide

## Multi-Agent Autonomous CLI

**Version:** 1.0.0  
**Document Type:** Installation Instructions  

---

## 1. Quick Start

### Windows (PowerShell)

```powershell
# Run the installer
.\setup-ma-cli.ps1

# Or download and run
Invoke-WebRequest -Uri "https://ma-cli.example.com/install.ps1" -OutFile "install.ps1"
.\install.ps1
```

### Linux/macOS

```bash
# Download and run installer
curl -fsSL https://ma-cli.example.com/install.sh | bash

# Or use pip
pip install ma-cli
```

---

## 2. System Requirements

### Minimum Requirements

| Component | Requirement | Notes |
|-----------|-------------|-------|
| OS | Windows 10+, macOS 11+, Linux | 64-bit required |
| Python | 3.11+ | Required for core runtime |
| Git | 2.0+ | For version control |
| Memory | 8GB RAM | 16GB recommended |
| Disk | 5GB free | More for models |

### Recommended Components

| Component | Purpose | Priority |
|-----------|---------|----------|
| Docker | Sandboxing | Optional |
| Ollama | Local models | Recommended |
| Node.js | MCP, plugins | Optional |
| Playwright | Browser automation | Optional |

---

## 3. Pre-Installation Checklist

Before installing MA-CLI, verify:

- [ ] Python 3.11+ is installed
- [ ] Git is installed and configured
- [ ] You have admin/sudo privileges
- [ ] Firewall allows outbound HTTPS
- [ ] Sufficient disk space available

### Verify Python

```bash
python --version
# Should show Python 3.11.x or higher
```

### Verify Git

```bash
git --version
# Should show git version 2.x.x
```

---

## 4. Installation Steps

### Step 1: Create Installation Directory

**Windows:**
```powershell
mkdir C:\MA-CLI
cd C:\MA-CLI
```

**Linux/macOS:**
```bash
sudo mkdir -p /opt/ma-cli
cd /opt/ma-cli
```

### Step 2: Clone Repository

```bash
git clone https://github.com/your-org/ma-cli.git .
```

### Step 3: Create Virtual Environment

**Windows:**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 5: Install MA-CLI

```bash
pip install -e .
```

### Step 6: Verify Installation

```bash
ma-cli --version
ma-cli doctor
```

---

## 5. Configuration

### Create Configuration File

Create `~/.ma-cli/config.yaml`:

```yaml
version: 1

runtime:
  autonomy_level: 3
  default_agent: native
  default_provider: omniroute

providers:
  ollama:
    type: openai-compatible
    enabled: true
    base_url: http://localhost:11434/v1

  omniroute:
    type: openai-compatible
    enabled: true
    base_url: http://localhost:20128/v1

  9router:
    type: openai-compatible
    enabled: true

models:
  aliases:
    claude-opus-5:
      provider: omniroute
    qwen-3.8:
      provider: ollama
```

### Set API Keys

```bash
# Never store keys in config file!
export ANTHROPIC_API_KEY="your-key-here"
export OPENAI_API_KEY="your-key-here"
export OMNIROUTE_API_KEY="your-key-here"
```

Or use the secrets manager:
```bash
ma-cli secrets set anthropic_api_key "your-key-here"
```

---

## 6. Provider Setup

### Ollama (Recommended for Local)

1. **Install Ollama:**
   ```bash
   # Windows/macOS
   curl https://ollama.ai/install.sh | sh
   
   # Or download from https://ollama.ai
   ```

2. **Pull Models:**
   ```bash
   ollama pull qwen2.5-coder:32b
   ollama pull deepseek-coder:33b
   ```

3. **Verify:**
   ```bash
   ollama list
   ```

### OmniRoute

1. **Clone Repository:**
   ```bash
   git clone https://github.com/diegosouzapw/OmniRoute.git
   cd OmniRoute
   ```

2. **Install and Configure:**
   ```bash
   # Follow OmniRoute installation instructions
   npm install
   npm start
   ```

3. **Configure API Keys:**
   - Add your provider API keys to OmniRoute
   - OmniRoute will aggregate them

### 9router

1. **Obtain Access:**
   - Sign up at 9router service
   - Get API credentials

2. **Configure:**
   ```bash
   export NINEROUTER_BASE_URL="https://api.9router.example.com"
   export NINEROUTER_API_KEY="your-key"
   ```

---

## 7. Post-Installation

### Run Doctor

```bash
ma-cli doctor
```

Expected output:
```
MA-CLI Doctor
=============

Runtime:
  ✓ Python 3.11.5
  ✓ MA-CLI 0.1.0

System:
  ✓ Git 2.40.1
  ✓ Docker 24.0.5 (optional)

Providers:
  ✓ Ollama connected (3 models)
  ⚠ OmniRoute not running
  ⚠ 9router not configured

Agents:
  ✓ NativeAgent ready
  ⚠ ClaudeAgent requires API key
  ⚠ CodexAgent requires API key

Status: READY (with warnings)
```

### Test Basic Commands

```bash
# Show help
ma-cli --help

# List agents
ma-cli agents

# List providers
ma-cli provider list

# List models
ma-cli model list
```

### Create First Project

```bash
mkdir my-project
cd my-project
ma-cli init
```

---

## 8. Troubleshooting

### Python Version Error

**Problem:** "Python 3.11+ required"

**Solution:**
```bash
# Check installed versions
python --version
python3 --version

# Install Python 3.11+
# Windows: Download from python.org
# macOS: brew install python@3.11
# Linux: apt install python3.11
```

### Permission Denied

**Problem:** "Permission denied" during installation

**Solution:**
```bash
# Linux/macOS
sudo chown -R $USER:$USER /opt/ma-cli

# Or install to user directory
pip install --user ma-cli
```

### Provider Connection Failed

**Problem:** "Cannot connect to provider"

**Solution:**
1. Check provider is running
2. Verify base URL is correct
3. Check firewall settings
4. Test with curl:
   ```bash
   curl http://localhost:11434/api/tags
   ```

### Model Not Found

**Problem:** "Model X not found"

**Solution:**
1. Pull the model (for Ollama):
   ```bash
   ollama pull qwen2.5-coder
   ```
2. Check model alias configuration
3. Run `ma-cli model list` to see available models

---

## 9. Uninstallation

### Windows

```powershell
# Deactivate virtual environment
deactivate

# Remove installation
Remove-Item -Recurse -Force C:\MA-CLI

# Remove user config
Remove-Item -Recurse -Force $env:USERPROFILE\.ma-cli

# Remove from PATH if added
```

### Linux/macOS

```bash
# Deactivate virtual environment
deactivate

# Remove installation
sudo rm -rf /opt/ma-cli

# Remove user config
rm -rf ~/.ma-cli

# Remove from PATH if needed
```

---

## 10. Update

### Check for Updates

```bash
ma-cli --version
```

### Update Installation

```bash
cd /path/to/ma-cli
git pull origin main
pip install -e . --upgrade
```

### Update Dependencies

```bash
pip install -r requirements.txt --upgrade
```

---

## 11. Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MA_CLI_CONFIG` | Config file path | `~/.ma-cli/config.yaml` |
| `MA_CLI_DATA` | Data directory | `~/.ma-cli` |
| `MA_CLI_LOG_LEVEL` | Logging level | `INFO` |
| `ANTHROPIC_API_KEY` | Anthropic API key | (required for Claude) |
| `OPENAI_API_KEY` | OpenAI API key | (required for Codex) |
| `OMNIROUTE_API_KEY` | OmniRoute API key | (required for OmniRoute) |
| `OLLAMA_HOST` | Ollama host | `localhost:11434` |

---

## 12. Next Steps

After installation:

1. **Run Doctor:** `ma-cli doctor`
2. **Configure Providers:** Set up Ollama, OmniRoute, etc.
3. **Test Native Agent:** `ma-cli run "Hello"`
4. **Read Documentation:** See `/docs` folder
5. **Join Community:** Check website for community links

---

**Document Owner:** MA-CLI Core Team  
**Last Updated:** Phase 1 Initiation
