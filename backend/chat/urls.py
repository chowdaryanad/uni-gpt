from django.urls import path
from .views import chat_page, chat_api_view, chat_stream_view

urlpatterns = [
    path("", chat_page, name="chat-page"),
    path("api/chat/", chat_api_view, name="chat-api"),
    path("api/chat/stream/", chat_stream_view, name="chat-stream"),
]
