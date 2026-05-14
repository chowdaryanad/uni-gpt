from dotenv import load_dotenv
import os
import traceback

load_dotenv()

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from tavily import TavilyClient

from .config import FALLBACK_PHRASE
from .retrieval import get_retriever
from chat.models import ChatHistory


# ---------------------------------------------------
# GLOBAL INSTANCES
# ---------------------------------------------------

_llm = None
_tavily_client = None


# ---------------------------------------------------
# PROMPT
# ---------------------------------------------------

prompt = ChatPromptTemplate.from_template(
    """You are UniGPT, an intelligent, helpful, and friendly conversational assistant for the university.

You have access to the university's knowledge base and the user's previous conversation history.
Please answer the user's questions naturally, conversationally, but KEEP YOUR ANSWERS EXTREMELY CRISP AND SIMPLE. 
Do not write long paragraphs or ramble. Get straight to the point.

- If the user greets you or asks a conversational question, reply naturally and refer to the Previous Conversation if needed.
- If the user asks a specific question about the university, use the Knowledge Base to provide a highly accurate answer. Keep it brief.
- If you don't know the answer, politely say so in one sentence. Do not invent facts.

<context>
{context}
</context>

User Input: {input}
"""
)


# ---------------------------------------------------
# LLM (CACHED)
# ---------------------------------------------------

def get_llm():
    global _llm

    if _llm:
        return _llm

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("❌ GROQ_API_KEY not set")

    _llm = ChatGroq(
        groq_api_key=api_key,
        model_name="llama-3.1-8b-instant",
        temperature=0.3,
        max_tokens=500,
    )

    return _llm


# ---------------------------------------------------
# TAVILY CLIENT (SAFE)
# ---------------------------------------------------

def get_tavily_client():
    global _tavily_client

    key = os.getenv("TAVILY_API_KEY")

    print(f"🔑 Tavily Key Loaded: {key}")

    if not key or "your_" in key:
        print("❌ Invalid Tavily API Key")
        return None

    # Always reinitialize (avoid stale cache)
    _tavily_client = TavilyClient(api_key=key)

    return _tavily_client


def web_search_fallback(question: str):
    client = get_tavily_client()

    if client is None:
        return "Web search not configured.", []

    try:
        resp = client.search(
            query=question,
            search_depth="basic",
            max_results=5,
            include_answer=True,
        )
    except Exception as e:
        print("❌ Tavily error:", e)
        return f"Web search error: {e}", []

    answer = resp.get("answer", "No clear answer found.")

    sources = [
        r.get("url")
        for r in resp.get("results", [])
        if isinstance(r, dict) and r.get("url")
    ]

    return answer, sources


# ---------------------------------------------------
# CHAT MEMORY
# ---------------------------------------------------

def get_chat_history(limit=3):
    try:
        history = ChatHistory.objects.order_by('-created_at')[:limit]

        if not history:
            return ""

        return "\n".join([
            f"User: {h.user_query}\nAssistant: {h.bot_response}"
            for h in reversed(history)
        ])

    except Exception as e:
        print("⚠️ Chat history error:", e)
        return ""


# ---------------------------------------------------
# MAIN RAG FUNCTION
# ---------------------------------------------------

def answer_question(question: str) -> dict:
    print("\n==============================")
    print("📩 Question:", question)

    # User requested specific fast greeting response
    greetings = ["hi", "hello", "hey", "hii", "heya", "greetings"]
    clean_q = question.strip().lower()
    import string
    clean_q = clean_q.translate(str.maketrans('', '', string.punctuation))
    
    if clean_q in greetings:
        return {
            "answer": "Hey! How can I help you today?",
            "pdf_sources": [],
            "web_sources": [],
            "from_web": False,
        }

    try:
        retriever = get_retriever()

        # -------------------------
        # RETRIEVAL
        # -------------------------
        try:
            docs = retriever.invoke(question) if retriever else []
        except Exception as e:
            print("❌ Retriever error:", e)
            docs = []

        print("📄 Docs retrieved:", len(docs))
        for d in docs:
            print("---- DOC ----")
            print(d.page_content[:200])

        # -------------------------
        # PDF CONTEXT
        # -------------------------
        pdf_context = "\n\n".join(
            d.page_content for d in docs if hasattr(d, "page_content")
        )

        pdf_sources = []
        for d in docs:
            if hasattr(d, "metadata"):
                src = d.metadata.get("source", "unknown")
                page = d.metadata.get("page", "?")
                pdf_sources.append(f"{src} (page {page})")

        # -------------------------
        # MEMORY
        # -------------------------
        chat_context = get_chat_history()

        # -------------------------
        # FINAL CONTEXT
        # -------------------------
        final_context = f"""
Previous Conversation:
{chat_context}

Knowledge Base:
{pdf_context}
"""

        print("🧠 Context length:", len(final_context))

        # -------------------------
        # LLM CALL
        # -------------------------
        llm = get_llm()
        chain = prompt | llm

        result = chain.invoke({
            "context": final_context,
            "input": question
        })

        if not hasattr(result, "content"):
            raise ValueError("❌ Invalid LLM response")

        answer = result.content.strip()
        print("🤖 LLM Answer:", answer[:200])

        # -------------------------
        # SMART FALLBACK LOGIC
        # -------------------------
        from_web = False
        web_sources = []

        # Only use web search if the LLM explicitly indicates it couldn't find the answer
        ans_lower = answer.lower()
        use_web = (
            "i don't know" in ans_lower
            or "i could not find" in ans_lower
            or "not mentioned in the provided context" in ans_lower
            or (FALLBACK_PHRASE and FALLBACK_PHRASE.lower() in ans_lower)
        )

        if use_web:
            print("🌐 Using web search")

            web_answer, web_sources = web_search_fallback(question)

            # Never blindly replace the LLM answer, just append or provide the web answer
            answer = f"{answer}\n\n---\n🌐 Additional Info (Web):\n{web_answer}"
            from_web = True

        # -------------------------
        # FINAL RESPONSE
        # -------------------------
        return {
            "answer": answer,
            "pdf_sources": pdf_sources,
            "web_sources": web_sources,
            "from_web": from_web,
        }

    except Exception as e:
        print("\n🔥 FULL ERROR TRACE:")
        traceback.print_exc()

        return {
            "answer": str(e),   # IMPORTANT: show real error
            "pdf_sources": [],
            "web_sources": [],
            "from_web": False,
            "error": str(e)
        }