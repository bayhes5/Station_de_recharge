from django.urls import path

from api.consumers import AdminSupervisionConsumer, TechnicianSupervisionConsumer

websocket_urlpatterns = [
    path("ws/admin/supervision/", AdminSupervisionConsumer.as_asgi()),
    path("ws/technician/supervision/", TechnicianSupervisionConsumer.as_asgi()),
]
