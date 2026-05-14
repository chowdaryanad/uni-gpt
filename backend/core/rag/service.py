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
    """You are a strict university assistant.

You MUST ONLY answer using the provided context.

If the answer is not clearly found in the context, respond EXACTLY with:
"I'm sorry, I could not find that information in the university guidelines."

Do NOT:

* add extra information
* mention technical issues
* act conversational
* invent anything

<context>
{context}
</context>

Question: {input}
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
        # STRICT OUTPUT VALIDATION
        # -------------------------
        if not answer or len(answer.strip()) < 5:
            answer = FALLBACK_PHRASE

        # If answer contains irrelevant phrases → reject it
        bad_patterns = [
            "technical difficulties",
            "I'm glad you're here",
            "I am here to help",
            "as an AI",
        ]

        if any(p.lower() in answer.lower() for p in bad_patterns):
            print("❌ LLM produced garbage → forcing fallback")
            answer = FALLBACK_PHRASE

        # -------------------------
        # SMART FALLBACK LOGIC
        # -------------------------
        from_web = False
        web_sources = []

        use_web = (
            not docs
            or len(pdf_context.strip()) < 50
            or (FALLBACK_PHRASE and FALLBACK_PHRASE in answer)
        )

        if use_web:
            print("🌐 Using web search")

            web_answer, web_sources = web_search_fallback(question)

            # Combine answers instead of replacing blindly
            if docs:
                answer = f"{answer}\n\n---\n🌐 Additional Info (Web):\n{web_answer}"
            else:
                answer = web_answer

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