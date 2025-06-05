from rest_framework.response import Response
from rest_framework import (
    viewsets, status, permissions
)
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework.permissions import IsAuthenticated
from django_filters import rest_framework as filters

from api.filters import RecipeFilter
from api.serializers import (
    IngredientSerializer, RecipeSerializer,
    RecipeCreateSerializer, FavoriteSerializer,
    ShoppingCartSerializer
)
from api.permissions import IsAuthorOrAdminOrReadOnly
from api.services import shopping_cart_pdf
from api.paginations import StandardResultsSetPagination
from recipes.models import (Recipe, Ingredient,
                            Favorite, ShoppingCart)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для работы с ингредиентами.
    Поддерживает только чтение (list и retrieve).
    Позволяет фильтровать ингредиенты по началу названия.
    """
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = None

    def get_queryset(self):
        name = self.request.query_params.get('name')
        if name:
            return self.queryset.filter(name__istartswith=name)
        return self.queryset


class RecipeViewSet(viewsets.ModelViewSet):
    """
    ViewSet для работы с рецептами.
    """
    queryset = Recipe.objects.all()
    pagination_class = StandardResultsSetPagination
    permission_classes = (IsAuthorOrAdminOrReadOnly,)
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = RecipeFilter

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return RecipeCreateSerializer
        return RecipeSerializer

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def favorite(self, request, pk=None):
        recipe = self.get_object()
        serializer = FavoriteSerializer(
            data={'recipe': recipe.id},
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @favorite.mapping.delete
    def delete_favorite(self, request, pk=None):
        recipe = self.get_object()
        deleted = Favorite.objects.filter(
            user=request.user,
            recipe=recipe
        ).delete()
        if not deleted[0]:
            return Response(
                {'detail': 'Рецепт не был найден в избранном.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def shopping_cart(self, request, pk=None):
        recipe = self.get_object()
        serializer = ShoppingCartSerializer(
            data={},
            context={
                'request': request,
                'recipe': recipe
            }
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @shopping_cart.mapping.delete
    def delete_shopping_cart(self, request, pk=None):
        recipe = get_object_or_404(Recipe, pk=pk)
        deleted = ShoppingCart.objects.filter(
            user=request.user,
            recipe=recipe
        ).delete()
        if not deleted[0]:
            return Response(
                {'message': 'Этот рецепт не найден в вашей корзине.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated]
    )
    def download_shopping_cart(self, request):
        """
        Скачать список покупок для выбранных рецептов в формате PDF,
        данные суммируются.
        """
        if ShoppingCart.objects.filter(user=request.user).exists():
            return shopping_cart_pdf(request)
        return Response('Список покупок пуст.', status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'], url_path='get-link')
    def get_recipe_link(self, request, pk=None):
        """
        Генерация абсолютной ссылки на рецепт.
        Возвращает полный URL для доступа к рецепту.
        """
        recipe = self.get_object()
        absolute_url = request.build_absolute_uri(
            reverse('recipes-detail', kwargs={'pk': recipe.id}))
        return Response({'short-link': absolute_url})
