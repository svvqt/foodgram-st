from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import EmailValidator
from django.contrib.auth.validators import UnicodeUsernameValidator

from users.constants import (
    MAX_USERNAME_LENGTH, MAX_FIRST_NAME_LENGTH,
    MAX_PASSWORD_LENGTH, MAX_SECOND_NAME_LENGTH)


class User(AbstractUser):
    """Модель пользователя.

    Регистрация с помощью email.
    """

    username = models.CharField(
        'Логин',
        max_length=MAX_USERNAME_LENGTH,
        unique=True,
        validators=[UnicodeUsernameValidator()],
    )
    first_name = models.CharField('Имя', max_length=MAX_FIRST_NAME_LENGTH)
    last_name = models.CharField('Фамилия', max_length=MAX_SECOND_NAME_LENGTH)
    email = models.EmailField(
        'email-адрес',
        unique=True,
        validators=[EmailValidator()]
    )
    password = models.CharField(max_length=MAX_PASSWORD_LENGTH, verbose_name='Пароль')
    avatar = models.ImageField(
        'Аватар',
        upload_to='avatars/',
        blank=True,
        null=True
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ['username']

    def __str__(self):
        return self.username
