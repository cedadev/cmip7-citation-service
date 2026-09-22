from rest_framework.authtoken.admin import TokenAdmin

TokenAdmin.raw_id_fields = ["user"]


from django.contrib import admin
from citations.models import ListenerPause, EditorPause

@admin.register(ListenerPause)
class ListenerPauseAdmin(admin.ModelAdmin):
    pass

@admin.register(EditorPause)
class EditorPauseAdmin(admin.ModelAdmin):
    pass