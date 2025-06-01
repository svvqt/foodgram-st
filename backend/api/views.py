from rest_framework.response import Response
from django.http import HttpResponse
from django.db.models import Sum
from rest_framework import (
    viewsets, status, permissions, mixins
)
from rest_framework.permissions import AllowAny
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.urls import reverse
from .paginations import StandardResultsSetPagination
from rest_framework.exceptions import PermissionDenied
from recipes.models import (Recipe, Ingredient,
                            Favorite, ShoppingCart, RecipeIngredient, User)
from .serializers import (
    IngredientSerializer, RecipeSerializer,
    RecipeCreateSerializer, FavoriteSerializer,
    ShoppingCartSerializer
)
from api.permissions import IsAuthorOrAdminOrReadOnly


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = None

    def get_queryset(self):
        name = self.request.query_params.get('name')
        if name:
            return self.queryset.filter(name__istartswith=name)
        return self.queryset


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    pagination_class = StandardResultsSetPagination
    permission_classes = (IsAuthorOrAdminOrReadOnly,)

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return RecipeCreateSerializer
        return RecipeSerializer

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if instance.author != request.user and not request.user.is_staff:
                raise PermissionDenied(
                    {"detail": "У вас нет прав изменять этот рецепт."}
                )
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.pop('partial', False))
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data)
        except PermissionDenied:
            return Response(
                {"detail": "У вас нет прав изменять этот рецепт."},
                status=status.HTTP_403_FORBIDDEN
            )

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        is_favorited = self.request.query_params.get('is_favorited')
        if is_favorited == '1' and user.is_authenticated:
            queryset = queryset.filter(in_favorites__user=user)

        is_in_shopping_cart = self.request.query_params.get(
            'is_in_shopping_cart'
        )
        if is_in_shopping_cart == '1' and user.is_authenticated:
            queryset = queryset.filter(in_shopping_carts__user=user)

        author_id = self.request.query_params.get('author')
        if author_id:
            queryset = queryset.filter(author_id=author_id)

        return queryset

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def favorite(self, request, pk=None):
        recipe = get_object_or_404(Recipe, pk=pk)
        user = request.user

        if request.method == 'POST':
            serializer = FavoriteSerializer(
                data={'user': request.user.id, 'recipe': recipe.id},
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )
        elif request.method == 'DELETE':
            try:
                favorite = Favorite.objects.get(user=user, recipe=recipe)
                favorite.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            except Favorite.DoesNotExist:
                return Response(
                    {'error': 'Рецепта нет в избранном.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def shopping_cart(self, request, pk=None):
        recipe = get_object_or_404(Recipe, pk=pk)
        user = request.user

        if request.method == 'POST':
            serializer = ShoppingCartSerializer(
                data={'user': request.user.id, 'recipe': recipe.id},
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )
        elif request.method == 'DELETE':
            try:
                cart_item = ShoppingCart.objects.get(user=user, recipe=recipe)
                cart_item.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            except ShoppingCart.DoesNotExist:
                return Response(
                    {'error': 'Рецепта нет в корзине покупок.'},
                    status=status.HTTP_400_BAD_REQUEST  # Возвращаем 400 вместо 404
                )

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def download_shopping_cart(self, request):
        ingredients = RecipeIngredient.objects.filter(
            recipe__in_shopping_carts__user=request.user
        ).values(
            'ingredient__name',
            'ingredient__measurement_unit'
        ).annotate(total_amount=Sum('amount'))

        shopping_list = []
        for item in ingredients:
            shopping_list.append(
                f"{item['ingredient__name']} - "
                f"{item['total_amount']} "
                f"{item['ingredient__measurement_unit']}"
            )

        response = HttpResponse(
            '\n'.join(shopping_list),
            content_type='text/plain'
        )
        response['Content-Disposition'] = (
            'attachment; filename="shopping_list.txt"'
        )
        return response

    @action(detail=True, methods=['get'], url_path='get-link')
    def get_recipe_link(self, request, pk=None):
        """Генерирует полную ссылку на рецепт."""
        recipe = self.get_object()
        absolute_url = request.build_absolute_uri(
            reverse('recipes-detail', kwargs={'pk': recipe.id}))
        return Response({'short-link': absolute_url})
