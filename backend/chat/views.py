from django.shortcuts import render
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
import json
import traceback

from core.rag.service import answer_question, stream_answer_question
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


# -------------------------------
# Streaming Chat API (SSE)
# -------------------------------
@csrf_exempt
def chat_stream_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    question = data.get("question")
    if not question or not isinstance(question, str):
        return JsonResponse({"error": "Invalid or missing question"}, status=400)

    question = question.strip()

    def event_stream():
        full_answer = []
        try:
            for token in stream_answer_question(question):
                full_answer.append(token)
                # SSE format: data: <payload>\n\n
                yield f"data: {json.dumps({'token': token})}\n\n"

            # Send done signal
            yield f"data: {json.dumps({'done': True})}\n\n"

            # Save complete answer to DB
            complete = "".join(full_answer).strip()
            if complete:
                ChatHistory.objects.create(
                    user_query=question,
                    bot_response=complete
                )
        except Exception as e:
            traceback.print_exc()
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    response = StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response