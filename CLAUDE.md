# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LinkAnaly is a LangBot plugin that parses links from chat messages and returns rich information about them. It supports Bilibili videos, GitHub repositories, and Gitee repositories.

The plugin is built on the LangBot Plugin SDK (https://docs.langbot.app/en/plugin/dev/tutor.html) and uses an event-driven architecture with EventListeners to handle incoming messages.

## Architecture

### Core Structure

- **main.py**: Plugin entry point, defines the `LinkAnaly` class that inherits from `BasePlugin`
- **manifest.yaml**: Plugin metadata and configuration, defines components, execution path, and plugin information
- **components/**: Component implementations loaded by the plugin system
  - **event_listener/default.py**: Main event handler that processes messages and dispatches to platform-specific handlers

### Event Handling Flow

1. Plugin receives `PersonMessageReceived` or `GroupMessageReceived` events
2. DefaultEventListener extracts text from message chain
3. Text is matched against registered link patterns (using regex)
4. Matching platform handler is invoked with the event context
5. Handler fetches data from platform API and replies with formatted message

### Platform Handlers

Each platform has:
- **Regex patterns**: List of URL patterns to match (defined in `link_handlers` dict)
- **Handler method**: Async function that takes `event_context` and `match` object
- **API integration**: HTTP requests to platform APIs (Bilibili API, GitHub API, Gitee API)

Platform handlers in `components/event_listener/default.py`:
- `handle_bilibili()`: Parses BV/av IDs, fetches video metadata, formats with emoji
- `handle_github()` / `handle_gitee()`: Call shared `_handle_git_repo()` with platform-specific API templates

## Development Commands

### Setup
```bash
pip install -r requirements.txt
```

### Debug Mode
Configure debug runtime in `.env` file (copy from `.env.example`):
```
DEBUG_RUNTIME_WS_URL=ws://localhost:5401/debug/ws
```

Then run the plugin with LangBot's debug runtime (refer to LangBot documentation for debug server setup).

### Distribution
Built artifacts are placed in `dist/` directory. The plugin is distributed through LangBot's plugin system.

## Adding New Platform Support

To add a new link parsing platform:

1. Add platform config to `link_handlers` dict in `DefaultEventListener.__init__()`:
   ```python
   "platform_name": {
       "patterns": [r"pattern1", r"pattern2"],
       "handler": self.handle_platform_name
   }
   ```

2. Implement handler method:
   ```python
   async def handle_platform_name(self, event_context: context.EventContext, match: re.Match):
       # Extract ID from match
       # Call platform API
       # Format response
       # Reply with platform_message.MessageChain
   ```

3. Use `_format_count()` utility for number formatting (converts 1000+ to K notation)
4. Handle errors gracefully with try/except and error reply messages
5. Update README.md with new platform in "支持平台" section

## Message Formatting

Replies use `platform_message.MessageChain` with:
- `platform_message.Plain(text=...)`: Text content
- `platform_message.Image(url=...)`: Image from URL

The plugin uses emoji prefixes for visual organization (🎐, 😃, 📝, 💖, etc.).
