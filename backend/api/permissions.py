from rest_framework import permissions


class IsAuthorOrAdminOrReadOnly(permissions.BasePermission):
    """
    Разрешает доступ на чтение всем пользователям.
    Разрешает изменение/удаление только автору объекта или администратору.
    """
    def has_permission(self, request, view):
        # Разрешаем безопасные методы (GET, HEAD, OPTIONS) всем
        # Для остальных методов пользователь должен быть аутентифицирован
        return (
            request.method in permissions.SAFE_METHODS or
            request.user and
            request.user.is_authenticated
        )

    def has_object_permission(self, request, view, obj):
        # Разрешаем безопасные методы всем
        if request.method in permissions.SAFE_METHODS:
            return True

        # Для изменений/удаления проверяем, что пользователь - автор или админ
        return (
            getattr(obj, 'author', None) == request.user or
            request.user.is_superuser
        )


class IsUserOrAdminOrReadOnly(permissions.BasePermission):
    """
    Разрешает доступ на чтение всем пользователям.
    Разрешает изменение/удаление только самому пользователю или администратору.
    Используется для профилей пользователей.
    """
    def has_permission(self, request, view):
        # Разрешаем безопасные методы всем
        # Для создания (POST) - только аутентифицированным
        # Для других методов проверяем в has_object_permission
        return (
            request.method in permissions.SAFE_METHODS or
            (request.user and request.user.is_authenticated)
        )

    def has_object_permission(self, request, view, obj):
        # Разрешаем безопасные методы всем
        if request.method in permissions.SAFE_METHODS:
            return True

        # Для изменений/удаления проверяем, что пользователь - владелец или админ
        return (
            obj == request.user or
            request.user.is_superuser
        )
