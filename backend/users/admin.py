from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from users.models import User


class UserAdmin(BaseUserAdmin):
    """
    Админ-зона пользователя с поддержкой смены пароля.
    Наследуется от BaseUserAdmin для корректной работы с пользователями.
    """
    list_display = ('id', 'username', 'first_name',
                    'last_name', 'email')
    search_fields = ('username', 'email')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    empty_value_display = '-пусто-'


admin.site.register(User, UserAdmin)
