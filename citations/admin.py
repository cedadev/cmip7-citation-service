from rest_framework.authtoken.admin import TokenAdmin

TokenAdmin.raw_id_fields = ["user"]


from django.contrib import admin
from citations.models import ListenerPause, PublisherPause

@admin.register(ListenerPause)
class ListenerPauseAdmin(admin.ModelAdmin):
    pass

@admin.register(PublisherPause)
class PublisherPauseAdmin(admin.ModelAdmin):
    pass