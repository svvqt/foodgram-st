from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from djoser.views import UserViewSet as DjoserUserViewSet
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from django.db.models import Prefetch
from rest_framework import status

from api.paginations import StandardResultsSetPagination
from recipes.models import Follow, Recipe
from users.models import User
from api.permissions import IsUserOrAdminOrReadOnly
from api.serializers import (
    CustomUserSerializer,
    FollowSerializer,
    UserAvatarSerializer,
    SubscribeSerializer
)


class UserViewSet(DjoserUserViewSet):
    """
    ViewSet для работы с пользователями, наследуемый от Djoser.
    Добавляет функционал подписок и работы с аватаром.
    """
    queryset = User.objects.all()
    serializer_class = CustomUserSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsUserOrAdminOrReadOnly]

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
                data={'author': author.id},
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

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
        follows = Follow.objects.filter(
            user=request.user
        ).select_related('author').prefetch_related(
            Prefetch('author__recipes', queryset=Recipe.objects.all())
        )
        
        page = self.paginate_queryset(follows)
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
