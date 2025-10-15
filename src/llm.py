"""
LLM code generator using Groq API.

This module handles:
1. Decoding base64 attachments from data URIs
2. Generating prompts for the LLM with context about brief, checks, and attachments
3. Calling Groq API to generate HTML/CSS/JS code
4. Parsing the response to extract index.html and README.md
"""

import base64
import logging
from typing import Dict, List, Any
from pathlib import Path
from groq import Groq

from .config import Config

logger = logging.getLogger(__name__)


class AttachmentDecoder:
    """Handles decoding and saving attachments from data URIs."""
    
    @staticmethod
    def decode(attachments: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Decode attachments from data URIs and save to disk.
        
        Args:
            attachments: List of {name: str, url: str} where url is a data URI
            
        Returns:
            List of {name, path, mime, size, preview} dictionaries
        """
        logger.info(f"Decoding {len(attachments)} attachments")
        saved = []
        
        for att in attachments:
            name = att.get("name", "attachment")
            url = att.get("url", "")
            
            if not url.startswith("data:"):
                logger.warning(f"Skipping non-data URI attachment: {name}")
                continue
            
            try:
                # Parse data URI: data:<mime>;base64,<data>
                header, b64_data = url.split(",", 1)
                mime = header.split(";")[0].replace("data:", "")
                data = base64.b64decode(b64_data)
                
                # Save to disk
                path = Config.ATTACHMENTS_DIR / name
                path.write_bytes(data)
                
                # Get preview for text files
                preview = AttachmentDecoder._get_preview(path, mime)
                
                saved.append({
                    "name": name,
                    "path": str(path),
                    "mime": mime,
                    "size": len(data),
                    "preview": preview
                })
                logger.info(f"Decoded attachment: {name} ({mime}, {len(data)} bytes)")
            except Exception as e:
                logger.error(f"Failed to decode attachment {name}: {e}")
        
        return saved
    
    @staticmethod
    def _get_preview(path: Path, mime: str) -> str:
        """Get a text preview of the attachment if it's readable."""
        if not mime.startswith("text") and not path.suffix in [".md", ".txt", ".csv", ".json"]:
            return f"[Binary file, {path.stat().st_size} bytes]"
        
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            # For CSV, show first few lines
            if path.suffix == ".csv":
                lines = text.split("\n")[:3]
                return "\\n".join(lines)
            # For others, show first 500 chars
            return text[:500]
        except Exception:
            return "[Could not read preview]"


class CodeGenerator:
    """Generates web application code using Groq LLM."""
    
    def __init__(self):
        self.client = Groq(api_key=Config.GROQ_API_KEY)
        self.model = "openai/gpt-oss-120b"
        logger.info(f"CodeGenerator initialized with model: {self.model}")
    
    def generate(
        self,
        brief: str,
        checks: List[str],
        attachments: List[Dict[str, str]],
        round_num: int,
        prev_readme: str = None
    ) -> Dict[str, str]:
        """
        Generate application code based on brief and requirements.
        
        Args:
            brief: Description of what the app should do
            checks: List of evaluation checks the app must pass
            attachments: List of attachment metadata (name, url as data URI)
            round_num: 1 for new app, 2+ for revisions
            prev_readme: Previous README for context (round 2+)
            
        Returns:
            Dictionary with keys: 'index.html', 'README.md', 'attachments'
        """
        logger.info(f"Generating code for round {round_num}: {brief[:80]}...")
        
        # Decode attachments
        saved_attachments = AttachmentDecoder.decode(attachments)
        
        # Build prompt
        prompt = self._build_prompt(brief, checks, saved_attachments, round_num, prev_readme)
        
        # Call Groq API
        try:
            logger.debug(f"Calling Groq API with {len(prompt)} char prompt")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert web developer. Generate clean, minimal, working HTML/CSS/JS code that meets requirements exactly."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=8000
            )
            
            generated_text = response.choices[0].message.content
            logger.info(f"Generated code using Groq ({len(generated_text)} chars)")
            
        except Exception as e:
            logger.error(f"Groq API error: {e}. Using fallback.")
            generated_text = self._fallback_html(brief, checks)
        
        # Parse response
        files = self._parse_response(generated_text, brief, checks, saved_attachments, round_num)
        files["attachments"] = saved_attachments
        
        return files
    
    def _build_prompt(
        self,
        brief: str,
        checks: List[str],
        attachments: List[Dict[str, Any]],
        round_num: int,
        prev_readme: str
    ) -> str:
        """Build the prompt for the LLM."""
        
        # Format attachments info
        att_info = "\n".join([
            f"- {att['name']} ({att['mime']}): {att['preview']}"
            for att in attachments
        ])
        
        # Format checks
        checks_info = "\n".join([f"- {check}" for check in checks])
        
        # Build context for round 2
        context = ""
        if round_num == 2 and prev_readme:
            context = f"""
## Previous Version Context
The app already exists. Here's the previous README:

{prev_readme}

Your task is to UPDATE the existing app based on the new requirements below.
"""
        
        return f"""Create a complete single-page web application.

## Round {round_num}

{context}

## Brief
{brief}

## Attachments Available
{att_info if att_info else "None"}

## Evaluation Checks
{checks_info}

## Output Requirements
1. Generate a SINGLE HTML file with inline CSS and JavaScript
2. The app must be fully functional and meet ALL evaluation checks
3. Use CDN links for any libraries (Bootstrap, marked, highlight.js, etc.)
4. After the HTML, add a line "---README---" and then provide a complete README.md

## README.md Must Include
- Project title and overview
- Features list
- How to use
- Technical details (libraries used, structure)
- License (MIT)

Output format:
```html
<!DOCTYPE html>
<html>
...
</html>
---README---
# Project Title
...
```

Generate the code now:"""
    
    def _parse_response(
        self,
        text: str,
        brief: str,
        checks: List[str],
        attachments: List[Dict[str, Any]],
        round_num: int
    ) -> Dict[str, str]:
        """Parse LLM response to extract HTML and README."""
        
        # Try to split on README marker
        if "---README---" in text:
            parts = text.split("---README---", 1)
            html_part = parts[0].strip()
            readme_part = parts[1].strip()
        else:
            html_part = text.strip()
            readme_part = self._generate_fallback_readme(brief, checks, attachments, round_num)
        
        # Clean code blocks
        html_part = self._strip_code_block(html_part)
        readme_part = self._strip_code_block(readme_part)
        
        return {
            "index.html": html_part,
            "README.md": readme_part
        }
    
    @staticmethod
    def _strip_code_block(text: str) -> str:
        """Remove markdown code block markers if present."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```) and potentially language identifier
            lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return text.strip()
    
    def _fallback_html(self, brief: str, checks: List[str]) -> str:
        """Generate minimal fallback HTML when API fails."""
        checks_html = "".join([f"<li>{check}</li>" for check in checks])
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fallback App</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <div class="container mt-5">
        <h1>Application (Fallback Mode)</h1>
        <div class="alert alert-warning">
            This is a fallback page generated because the LLM API was unavailable.
        </div>
        <h2>Brief</h2>
        <p>{brief}</p>
        <h2>Checks to Implement</h2>
        <ul>{checks_html}</ul>
    </div>
</body>
</html>
---README---
{self._generate_fallback_readme(brief, checks, [], 1)}"""
    
    def _generate_fallback_readme(
        self,
        brief: str,
        checks: List[str],
        attachments: List[Dict[str, Any]],
        round_num: int
    ) -> str:
        """Generate a basic README when LLM doesn't provide one."""
        att_list = "\n".join([f"- {att['name']}" for att in attachments])
        checks_list = "\n".join([f"- {check}" for check in checks])
        
        return f"""# Auto-Generated Application (Round {round_num})

## Overview
{brief}

## Attachments
{att_list if att_list else "None"}

## Evaluation Checks
{checks_list}

## Usage
1. Open `index.html` in a web browser
2. The application should be fully functional

## Technical Details
- Single-page application
- No build process required
- All dependencies loaded from CDN

## License
MIT License
"""
