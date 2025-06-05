from rest_framework import permissions


class IsAuthorOrAdminOrReadOnly(permissions.BasePermission):
    """
    Разрешает доступ на чтение всем пользователям.
    Запись разрешена только автору объекта или администратору.
    """

    def has_permission(self, request, view):
        """Проверяет общие права доступа к представлению."""
        return (
            request.method in permissions.SAFE_METHODS
            or request.user
            and request.user.is_authenticated
        )

    def has_object_permission(self, request, view, obj):
        """Проверяет права доступа к конкретному объекту."""
        if request.method in permissions.SAFE_METHODS:
            return True

        return (
            getattr(obj, 'author', None) == request.user
            or request.user.is_superuser
        )


class IsUserOrAdminOrReadOnly(permissions.BasePermission):
    """
    Разрешает доступ на чтение всем пользователям.
    Запись разрешена только самому пользователю или администратору.
    Используется для работы с профилями пользователей.
    """

    def has_permission(self, request, view):
        """Проверяет общие права доступа к представлению."""
        return (
            request.method in permissions.SAFE_METHODS
            or request.user
            and request.user.is_authenticated
        )

    def has_object_permission(self, request, view, obj):
        """Проверяет права доступа к конкретному объекту."""
        if request.method in permissions.SAFE_METHODS:
            return True

        return obj == request.user or request.user.is_superuser