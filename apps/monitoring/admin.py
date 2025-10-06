from django.contrib import admin
from .models import SessionEvent

@admin.register(SessionEvent)
class SessionEventAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "ts", "ip")
    list_filter  = ("event", "ts")
    search_fields = ("user__username", "ip", "user_agent")
