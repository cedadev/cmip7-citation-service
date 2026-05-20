"""
URL configuration for citation_site project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from allauth.socialaccount.providers.github.views import oauth2_login
from django.conf import settings
from django.conf.urls import handler403, handler404, handler500
from django.contrib import admin
from django.contrib.auth.models import User
from django.shortcuts import render
from django.urls import include, path
from django.views.generic import RedirectView
from rest_framework import routers, serializers, viewsets


# Serializers define the API representation.
class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ['url', 'username', 'email', 'is_staff']

# ViewSets define the view behavior.
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register(r'users', UserViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(('citations.urls','citations'), namespace='citations')),
    path("accounts/login/", oauth2_login, name="account_login"),
    path("accounts/profile/", RedirectView.as_view(pattern_name="citations:citations", permanent=True)),
    path('accounts/', include('allauth.urls')),
]

def custom_404(request, exception):

    if settings.USE_CEDA_BRANDING:
        template_base = 'fwtheme_django/layout.html'
    else:
        template_base = 'bases/generic_base.html'


    return render(request, "404.html", {
        "reason": str(exception),
        "template_base":template_base,
    }, status=404)

def custom_403(request, exception):

    if settings.USE_CEDA_BRANDING:
        template_base = 'fwtheme_django/layout.html'
    else:
        template_base = 'bases/generic_base.html'

    return render(request, "403.html", {
        "reason": str(exception),
        "template_base":template_base,
    }, status=403)

def custom_500(request):
    if settings.USE_CEDA_BRANDING:
        template_base = 'fwtheme_django/layout.html'
    else:
        template_base = 'bases/generic_base.html'

    return render(request, "500.html", {
        "reason": "Internal Server Error - Contact the CEDA Helpdesk",
        "template_base":template_base,
    }, status=500)

handler404 = custom_404

handler403 = custom_403

handler500 = custom_500
