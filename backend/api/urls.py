from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter
from .views import RecipeViewSet, IngredientViewSet

from users.views import UserViewSet


router = DefaultRouter()
router.register('users', UserViewSet, basename='users')
router.register('recipes', RecipeViewSet, basename='recipes')
router.register('ingredients', IngredientViewSet, basename='ingredients')

urlpatterns = [
    path('', include(router.urls)),
    re_path('auth/', include('djoser.urls.authtoken')),
]
