
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

from accounts import views as accounts_views

urlpatterns = [
    path('admin/', admin.site.urls),

    path(
        '.well-known/assetlinks.json',
        accounts_views.assetlinks_json,
        name='assetlinks_json'
    ),

    path('api/', include('api.urls')),

    path('', include('accounts.urls')),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
else:
    media_prefix = settings.MEDIA_URL.lstrip('/')
    urlpatterns += [
        re_path(
            rf'^{media_prefix}(?P<path>.*)$',
            serve,
            {'document_root': settings.MEDIA_ROOT},
        ),
    ]
