from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from accounts import views as accounts_views


def assetlinks_view(request):
    data = [
        {
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": "com.nemsu.clinicconnect",
                "sha256_cert_fingerprints": [
                    "PASTE_YOUR_SHA256_FINGERPRINT_HERE"
                ],
            },
        }
    ]
    return JsonResponse(data, safe=False)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('.well-known/assetlinks.json', assetlinks_view, name='assetlinks'),
    path('', include('accounts.urls')),
    path(".well-known/assetlinks.json", accounts_views.assetlinks_json, name="assetlinks_json"),
]
    

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )