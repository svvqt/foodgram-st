from rest_framework.response import Response
from rest_framework import (
    viewsets, status, permissions
)
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework.permissions import (
    AllowAny, IsAuthenticated,
    IsAuthenticatedOrReadOnly
)
from django_filters import rest_framework as filters
from djoser.views import UserViewSet as DjoserUserViewSet
from django.db.models import Prefetch

from api.filters import RecipeFilter
from api.serializers import (
    IngredientSerializer, RecipeSerializer,
    RecipeCreateSerializer, FavoriteSerializer,
    ShoppingCartSerializer, CustomUserSerializer,
    FollowSerializer, UserAvatarSerializer,
    SubscribeSerializer
)
from api.permissions import IsAuthorOrAdminOrReadOnly, IsUserOrAdminOrReadOnly
from api.services import shopping_cart_pdf
from api.paginations import StandardResultsSetPagination
from recipes.models import (Recipe, Ingredient,
                            Favorite, ShoppingCart, Follow)
from users.models import User


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для работы с ингредиентами.

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
    """ViewSet для работы с рецептами."""

    queryset = Recipe.objects.all()
    pagination_class = StandardResultsSetPagination
    permission_classes = (
        IsAuthorOrAdminOrReadOnly,
        IsAuthenticatedOrReadOnly,
    )
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = RecipeFilter

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return RecipeCreateSerializer
        return RecipeSerializer

    def _add_to_relation(self, request, pk, serializer_class, model):
        """Общий метод для добавления в избранное/корзину."""

        recipe = self.get_object()

        data = {
            'user': request.user.id,
            'recipe': recipe.id
        }

        serializer = serializer_class(
            data=data,
            context={'request': request, 'recipe': recipe}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _remove_from_relation(self, request, pk, model_class, error_message):
        """Общий метод для удаления из избранного/корзины."""

        recipe = self.get_object() if model_class == Favorite else get_object_or_404(Recipe, pk=pk)
        deleted = model_class.objects.filter(
            user=request.user,
            recipe=recipe
        ).delete()
        if not deleted[0]:
            return Response(
                {'detail': error_message},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def favorite(self, request, pk=None):
        return self._add_to_relation(request, pk, FavoriteSerializer, Favorite)

    @favorite.mapping.delete
    def delete_favorite(self, request, pk=None):
        return self._remove_from_relation(
            request, pk, Favorite, 'Рецепт не был найден в избранном.'
        )

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def shopping_cart(self, request, pk=None):
        return self._add_to_relation(request, pk, ShoppingCartSerializer, ShoppingCart)

    @shopping_cart.mapping.delete
    def delete_shopping_cart(self, request, pk=None):
        return self._remove_from_relation(
            request, pk, ShoppingCart, 'Этот рецепт не найден в вашей корзине.'
        )

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated]
    )
    def download_shopping_cart(self, request):
        """Скачать список покупок для выбранных рецептов в формате PDF.

        Данные суммируются.
        """

        if ShoppingCart.objects.filter(user=request.user).exists():
            return shopping_cart_pdf(request)
        return Response('Список покупок пуст.', status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'], url_path='get-link')
    def get_recipe_link(self, request, pk=None):
        """Генерация абсолютной ссылки на рецепт.

        Возвращает полный URL для доступа к рецепту.
        """

        recipe = self.get_object()
        absolute_url = request.build_absolute_uri(
            reverse('recipes-detail', kwargs={'pk': recipe.id}))
        return Response({'short-link': absolute_url})


class UserViewSet(DjoserUserViewSet):
    """ViewSet для работы с пользователями, наследуемый от Djoser.

    Добавляет функционал подписок и работы с аватаром.
    """

    queryset = User.objects.all()
    serializer_class = CustomUserSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = (IsUserOrAdminOrReadOnly, IsAuthenticatedOrReadOnly,)

    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        if self.action == 'me':
            return [IsAuthenticated()]
        return super().get_permissions()

    @action(detail=True,
            methods=['post', 'delete'],
            permission_classes=[IsAuthenticated],)
    def subscribe(self, request, id=None):
        """Оформление/отмена подписки на пользователя."""

        author = get_object_or_404(User, id=id)
        user = request.user

        if request.method == 'POST':
            serializer = SubscribeSerializer(
                data={'author': author.id, 'user': user.id},
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )

        # DELETE method
        deleted = Follow.objects.filter(user=user, author=author).delete()
        if not deleted[0]:
            return Response(
                {'errors': 'Подписки не существует.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False,
            methods=['get'],
            permission_classes=[IsAuthenticated])
    def subscriptions(self, request):
        """Получение списка всех подписок текущего пользователя."""

        subscribed_users = User.objects.filter(
            followed__user=request.user
            ).prefetch_related(
                Prefetch('recipes', queryset=Recipe.objects.all())
            )

        page = self.paginate_queryset(subscribed_users)
        serializer = FollowSerializer(
            page,
            many=True,
            context={'request': request}
        )
        return self.get_paginated_response(serializer.data)

    @action(
        detail=False,
        methods=['put', 'delete'],
        url_path='me/avatar',
        permission_classes=[IsAuthenticated]
    )
    def avatar(self, request):
        """Обновление или удаление аватара текущего пользователя."""

        user = request.user

        if request.method == 'DELETE':
            user.avatar.delete()
            user.save()
            return Response(status=status.HTTP_204_NO_CONTENT)

        if 'avatar' not in request.data:
            return Response( 
                {"avatar": ["Это поле обязательно."]},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = UserAvatarSerializer(
            user,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
