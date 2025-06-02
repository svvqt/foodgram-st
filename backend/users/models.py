from django.db import models

from django.contrib.auth.models import AbstractUser
from django.core.validators import MinLengthValidator, EmailValidator


class User(AbstractUser):
    """
    Модель пользователя.
    Регистрация с помощью email.
    """
    USER = 'user'
    ADMIN = 'admin'
    ROLE_USER = [
        (USER, 'Пользователь'),
        (ADMIN, 'Администратор')
    ]
    username = models.CharField('Логин', max_length=150,
                                unique=True,
                                validators=[MinLengthValidator(3)])
    first_name = models.CharField('Имя', max_length=150)
    last_name = models.CharField('Фамилия', max_length=150)
    email = models.EmailField('email-адрес',
                              unique=True,
                              validators=[EmailValidator()])
    role = models.CharField(max_length=15, choices=ROLE_USER,
                            default=USER, verbose_name='Пользовательская роль')
    password = models.CharField(max_length=150,
                                verbose_name='Пароль',
                                validators=[MinLengthValidator(8)])
    avatar = models.ImageField(
        'Аватар',
        upload_to='avatars/',
        blank=True,
        null=True
    )
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'password', 'first_name', 'last_name']

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    @property
    def admin(self):
        return self.role == self.ADMIN or self.is_superuser

    def __str__(self):
        return self.username
