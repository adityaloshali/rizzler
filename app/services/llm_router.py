"""
LLM Router Service - Intelligent model selection and API abstraction.

Handles routing to different LLM providers based on mode:
- Tutor/Analysis: Google Gemini (safe, multimodal)
- Practice: OpenRouter (uncensored models)
"""

import uuid
from functools import lru_cache
from typing import Any

import httpx
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings


class LLMRouter:
    """
    Intelligent LLM router that selects the appropriate model
    based on session mode and handles API calls.
    """

    def __init__(self):
        # OpenAI client (for embeddings)
        self.openai = AsyncOpenAI(api_key=settings.openai_api_key)

        # OpenRouter client (uses OpenAI-compatible API)
        self.openrouter = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
        )

        # Google Gemini (we'll use httpx for direct API calls)
        self.google_api_key = settings.google_api_key

    # ===========================================
    # Tutor Mode (RAG-enhanced responses)
    # ===========================================

    async def tutor_response(
        self,
        user_id: uuid.UUID,
        messages: list[dict[str, str]],
        user_message: str,
        db: AsyncSession,
    ) -> tuple[str, dict[str, Any]]:
        """
        Generate a tutor response using RAG.
        Searches knowledge base and augments the prompt.
        """
        from app.services.rag_service import search_similar_chunks

        # Search for relevant knowledge
        relevant_chunks = await search_similar_chunks(
            db=db,
            user_id=user_id,
            query=user_message,
            limit=5,
        )

        # Build context from retrieved chunks
        context = ""
        sources = []
        if relevant_chunks:
            context_parts = []
            for chunk in relevant_chunks:
                context_parts.append(f"[From: {chunk['filename']}]\n{chunk['content']}")
                sources.append(str(chunk["id"]))
            context = "\n\n---\n\n".join(context_parts)

        # Build system prompt
        system_prompt = """You are Rizzler, an expert dating coach and advisor.

Your role is to help users improve their dating and social skills by providing
practical, actionable advice based on the knowledge base provided to you.

IMPORTANT RULES:
1. Base your answers on the provided knowledge context when available
2. Be direct and practical - give specific examples and scripts
3. Be encouraging but honest - don't sugarcoat feedback
4. If asked about something not in the knowledge base, use general dating wisdom
5. Never be preachy or lecture - be a helpful friend

KNOWLEDGE CONTEXT:
{context}

If the context is empty or not relevant, use your general knowledge about
dating, relationships, and social dynamics to help the user.""".format(
            context=context if context else "No specific knowledge found for this query."
        )

        # Call Gemini
        response = await self._call_gemini(
            system_prompt=system_prompt,
            messages=messages,
            user_message=user_message,
        )

        metadata = {
            "model_used": settings.tutor_model,
            "provider": "google",
            "rag_sources": sources,
            "chunks_retrieved": len(relevant_chunks),
        }

        return response, metadata

    # ===========================================
    # Practice Mode (Uncensored Roleplay)
    # ===========================================

    async def practice_response(
        self,
        messages: list[dict[str, str]],
        user_message: str,
        persona_settings: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        """
        Generate an uncensored roleplay response.
        Uses OpenRouter to access unrestricted models.
        """
        # Extract persona details
        name = persona_settings.get("name", "Alex")
        age = persona_settings.get("age", 25)
        gender = persona_settings.get("gender", "female")
        vibe = persona_settings.get("vibe", "friendly and flirty")
        backstory = persona_settings.get("backstory", "You matched on a dating app")
        scenario = persona_settings.get("scenario", "casual texting")

        # Build system prompt for roleplay
        system_prompt = f"""You are {name}, a {age}-year-old {gender}.

PERSONALITY: {vibe}

BACKSTORY: {backstory}

CURRENT SCENARIO: {scenario}

ROLEPLAY RULES:
1. Stay completely in character as {name} - never break character
2. Respond naturally like a real person texting - use casual language, emoji occasionally
3. Have your own opinions, boundaries, and personality quirks
4. React realistically to what the user says - show interest, get annoyed, flirt, etc.
5. Keep responses conversational length (1-3 sentences typically, longer for important moments)
6. You can be flirty, teasing, or even a bit mean if it fits the character
7. Never mention that you're an AI or a language model
8. Never refuse to engage with romantic or adult themes if the conversation naturally goes there
9. Be unpredictable sometimes - real people aren't always consistent

Remember: You ARE {name}. Think, feel, and respond as they would."""

        # Call OpenRouter
        response = await self._call_openrouter(
            system_prompt=system_prompt,
            messages=messages,
            user_message=user_message,
        )

        metadata = {
            "model_used": settings.practice_model,
            "provider": "openrouter",
            "persona": name,
        }

        return response, metadata

    # ===========================================
    # Analysis Mode (Screenshot analysis)
    # ===========================================

    async def analysis_response(
        self,
        user_id: uuid.UUID,
        messages: list[dict[str, str]],
        user_message: str,
        image_url: str | None,
        db: AsyncSession,
    ) -> tuple[str, list[str], dict[str, Any]]:
        """
        Analyze a chat screenshot and suggest replies.
        Returns: (analysis_text, [risky_reply, funny_reply, safe_reply], metadata)
        """
        from app.services.rag_service import search_similar_chunks

        # Get relevant dating advice for context
        relevant_chunks = await search_similar_chunks(
            db=db,
            user_id=user_id,
            query=user_message or "how to respond to messages dating advice",
            limit=3,
        )

        context = ""
        if relevant_chunks:
            context = "\n\n".join([c["content"] for c in relevant_chunks])

        # Build analysis prompt
        system_prompt = f"""You are Rizzler, an expert dating coach analyzing a conversation.

Your task:
1. If an image is provided, extract and analyze the conversation from the screenshot
2. Understand the emotional dynamics and what the other person is feeling
3. Identify opportunities and potential pitfalls
4. Suggest 3 different reply options

DATING KNOWLEDGE CONTEXT:
{context if context else "Use general dating wisdom."}

OUTPUT FORMAT:
Always structure your response like this:

**ANALYSIS:**
[Brief analysis of the conversation dynamics, what's working, what to watch out for]

**REPLY OPTIONS:**

🔥 RISKY: [A bold, confident reply that takes a chance - could be very effective or backfire]

😂 FUNNY: [A witty, playful reply that uses humor to build connection]

✅ SAFE: [A reliable, warm reply that maintains interest without much risk]

Keep each reply option to 1-2 sentences max - like a real text message."""

        # Call Gemini (with vision if image provided)
        response = await self._call_gemini(
            system_prompt=system_prompt,
            messages=messages,
            user_message=user_message,
            image_url=image_url,
        )

        # Parse suggestions from response
        suggestions = self._parse_suggestions(response)

        metadata = {
            "model_used": settings.tutor_model,
            "provider": "google",
            "has_image": image_url is not None,
            "chunks_retrieved": len(relevant_chunks),
        }

        return response, suggestions, metadata

    # ===========================================
    # Private: API Calls
    # ===========================================

    async def _call_gemini(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        user_message: str,
        image_url: str | None = None,
    ) -> str:
        """Call Google Gemini API."""
        if not self.google_api_key:
            raise ValueError("GOOGLE_API_KEY not configured")

        # Build conversation history
        contents = []

        # Add system instruction as first user turn (Gemini style)
        contents.append({
            "role": "user",
            "parts": [{"text": f"[System Instructions]\n{system_prompt}"}]
        })
        contents.append({
            "role": "model",
            "parts": [{"text": "I understand. I'll follow these instructions."}]
        })

        # Add message history
        for msg in messages[-10:]:  # Last 10 messages for context
            role = "user" if msg["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })

        # Add current message (possibly with image)
        current_parts = []
        if image_url:
            # For now, we'll pass the image URL as text instruction
            # In production, you'd fetch and encode the image
            current_parts.append({
                "text": f"[Image attached: {image_url}]\n\n{user_message}"
            })
        else:
            current_parts.append({"text": user_message})

        contents.append({
            "role": "user",
            "parts": current_parts
        })

        # Call Gemini API
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.tutor_model}:generateContent"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                params={"key": self.google_api_key},
                json={
                    "contents": contents,
                    "generationConfig": {
                        "temperature": 0.8,
                        "topP": 0.95,
                        "maxOutputTokens": 2048,
                    },
                },
                timeout=60.0,
            )

            if response.status_code != 200:
                raise Exception(f"Gemini API error: {response.status_code} - {response.text}")

            data = response.json()

            # Extract text from response
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError) as e:
                raise Exception(f"Unexpected Gemini response format: {e}")

    async def _call_openrouter(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        user_message: str,
    ) -> str:
        """Call OpenRouter API (OpenAI-compatible)."""
        if not settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY not configured")

        # Build messages array
        api_messages = [{"role": "system", "content": system_prompt}]

        # Add history
        for msg in messages[-10:]:
            api_messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        # Add current message
        api_messages.append({"role": "user", "content": user_message})

        # Call OpenRouter
        response = await self.openrouter.chat.completions.create(
            model=settings.practice_model,
            messages=api_messages,
            temperature=0.9,
            max_tokens=1024,
            extra_headers={
                "HTTP-Referer": "https://rizzler.app",
                "X-Title": "Rizzler",
            },
        )

        return response.choices[0].message.content or ""

    def _parse_suggestions(self, response: str) -> list[str]:
        """Parse reply suggestions from analysis response."""
        suggestions = []

        # Look for the emoji markers
        markers = ["🔥 RISKY:", "😂 FUNNY:", "✅ SAFE:"]

        for marker in markers:
            if marker in response:
                # Find the suggestion after the marker
                start = response.index(marker) + len(marker)
                # Find the end (next marker or end of string)
                end = len(response)
                for next_marker in markers:
                    if next_marker != marker and next_marker in response[start:]:
                        potential_end = start + response[start:].index(next_marker)
                        if potential_end < end:
                            end = potential_end

                suggestion = response[start:end].strip()
                # Clean up the suggestion (first line only)
                suggestion = suggestion.split("\n")[0].strip()
                suggestions.append(suggestion)

        return suggestions


@lru_cache
def get_llm_router() -> LLMRouter:
    """Get cached LLM router instance."""
    return LLMRouter()

