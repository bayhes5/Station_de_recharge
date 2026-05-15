from django.urls import path

from api.consumers import AdminSupervisionConsumer

websocket_urlpatterns = [
    path("ws/admin/supervision/", AdminSupervisionConsumer.as_asgi()),
]
