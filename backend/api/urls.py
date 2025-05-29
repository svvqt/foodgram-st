from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter
from django.views.generic import TemplateView
from .views import RecipeViewSet, IngredientViewSet
from users.views import UserViewSet
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="Foodgram API",
        default_version='v1',
    ),
    public=True,
)

router = DefaultRouter()
router.register('users', UserViewSet)
router.register('recipes', RecipeViewSet, basename='recipes')
router.register('ingredients', IngredientViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('api/docs/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    re_path(r'auth/', include('djoser.urls.authtoken')),
]
