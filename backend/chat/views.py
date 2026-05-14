from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import traceback

from core.rag.service import answer_question
from .models import ChatHistory


# -------------------------------
# Render Chat UI Page
# -------------------------------
def chat_page(request):
    return render(request, "chat.html")


# -------------------------------
# Chat API Endpoint
# -------------------------------
@csrf_exempt
def chat_api_view(request):

    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    # Parse JSON safely
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    question = data.get("question")

    if not question or not isinstance(question, str):
        return JsonResponse({"error": "Invalid or missing question"}, status=400)

    question = question.strip()

    try:
        print(f"[DEBUG] Incoming question: {question}")

        # 🔥 CALL YOUR RAG PIPELINE
        result = answer_question(question)

        print(f"[DEBUG] Raw result: {result}")

        # 🚨 Validate result (you weren't doing this)
        if result is None:
            raise ValueError("answer_question returned None")

        if not isinstance(result, dict):
            raise ValueError(f"Invalid response format: {type(result)}")

        answer = result.get("answer")

        if not answer:
            raise ValueError("No 'answer' field in result")

        # ✅ Save chat history
        ChatHistory.objects.create(
            user_query=question,
            bot_response=answer
        )

        return JsonResponse({
            "answer": answer
        }, status=200)

    except Exception as e:
        # 🔥 THIS is what you were missing
        traceback.print_exc()

        return JsonResponse({
            "error": str(e)
        }, status=500)