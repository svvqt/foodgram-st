from rest_framework import viewsets, status, permissions
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.decorators import action
from djoser.serializers import SetPasswordSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import AuthenticationFailed
from django.shortcuts import get_object_or_404
from api.paginations import StandardResultsSetPagination
from recipes.models import Follow
from users.models import User
from users.serializers import (
    UserSerializer,
    FollowSerializer,
    UserAvatarSerializer,
    UserCreateSerializer
)
from api.permissions import IsUserOrAdminOrReadOnly


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet для работы с пользователями.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = StandardResultsSetPagination

    # Динамически выбираем пермишены
    def get_permissions(self):
        if self.action == 'create':
            # Для создания пользователя разрешаем всем
            return [permissions.AllowAny()]
        # Для остальных действий используем кастомный пермишен
        return [IsUserOrAdminOrReadOnly()]

    # Используем другой сериализатор для создания
    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return super().get_serializer_class()

    @action(detail=False,
            methods=['get'],
            permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        """Получение данных текущего аутентифицированного пользователя."""
        if not request.user.is_authenticated:
            raise AuthenticationFailed("Требуется авторизация")
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(["post"],
            detail=False,
            permission_classes=[IsAuthenticated])
    def set_password(self, request, *args, **kwargs):
        """Изменение пароля текущего пользователя."""
        serializer = SetPasswordSerializer(
            data=request.data,
            context={'request': request})
        if serializer.is_valid(raise_exception=True):
            self.request.user.set_password(serializer.data["new_password"])
            self.request.user.save()
            return Response('Пароль успешно изменен',
                            status=status.HTTP_204_NO_CONTENT)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True,
            methods=['post', 'delete'],
            permission_classes=[permissions.IsAuthenticated])
    def subscribe(self, request, pk=None):
        """Оформление/отмена подписки на пользователя."""
        author = get_object_or_404(User, pk=pk)
        user = request.user

        if request.method == 'POST':
            # Проверка существующей подписки
            if Follow.objects.filter(user=user, author=author).exists():
                return Response(
                    {'errors': 'Вы уже подписаны на этого пользователя!'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if user == author:
                return Response(
                    {'errors': 'Невозможно подписаться на себя!'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Создание подписки
            follow = Follow.objects.create(user=user, author=author)

            # Сериализуем данные подписки
            serializer = FollowSerializer(
                follow,
                context={'request': request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        elif request.method == 'DELETE':
            # Удаление подписки
            try:
                subscription = Follow.objects.get(user=user, author=author)
                subscription.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            except Follow.DoesNotExist:
                return Response(
                    {'errors': 'Подписка не существует.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

    @action(detail=False,
            methods=['get'],
            permission_classes=[permissions.IsAuthenticated])
    def subscriptions(self, request):
        """Получение списка всех подписок текущего пользователя."""
        if not request.user.is_authenticated:
            return Response(
                {'detail': 'Authentication credentials were not provided.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        follows = Follow.objects.filter(
            user=request.user
        ).order_by('-id').select_related('author')

        # Пагинация
        page = self.paginate_queryset(follows)
        serializer = FollowSerializer(
            page if page is not None else follows,
            many=True,
            context={'request': request}
        )

        return self.get_paginated_response(serializer.data) if page is not None else Response(serializer.data)

    @action(
        detail=False,
        methods=['put', 'delete'],
        url_path='me/avatar',
        permission_classes=[IsAuthenticated],
        parser_classes=[JSONParser]
    )
    def avatar(self, request):
        """Обновление или удаление аватара текущего пользователя."""
        user = request.user

        if request.method == 'DELETE':
            user.avatar.delete()  # Удаляет файл и записывает NULL в БД
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
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
