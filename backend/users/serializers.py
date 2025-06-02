from rest_framework import serializers
from rest_framework import status
from rest_framework.exceptions import ValidationError
from drf_extra_fields.fields import Base64ImageField
from django.core.validators import RegexValidator
from django.core.validators import MinLengthValidator
from recipes.models import Follow
from users.models import User


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Сериализатор для создания пользователя.
    Включает валидацию username и email на уникальность.
    Пароль сохраняется в хэшированном виде.
    """
    username = serializers.CharField(
        max_length=150,
        validators=[
            RegexValidator(
                regex=r'^[\w.@+-]+$',  # только буквы, цифры, @/./+/-/_
                message='Username может содержать только буквы, цифры и \
                    @/./+/-/_',
                code='invalid_username'
            ),
            MinLengthValidator(3,
                               message='Username должен быть не короче 3\
                                  символов.'
                               )
        ]
    )

    class Meta:
        model = User
        fields = ('email', 'username', 'first_name', 'last_name', 'password')
        extra_kwargs = {'password': {'write_only': True}} # Пароль не возвращается в ответе

    def validate_username(self, value):
        """Проверка уникальности username и длины."""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                'Пользователь с таким username уже существует.'
                )
        if len(value) > 150:
            raise serializers.ValidationError(
                'Username не может быть длиннее 150 символов.'
                )
        return value

    def validate_email(self, value):
        """Проверка уникальности email."""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                'Пользователь с таким email уже существует.'
                )
        return value

    def create(self, validated_data):
        """Создание пользователя с хэшированием пароля."""
        user = User.objects.create_user(**validated_data)
        return user

    def to_representation(self, instance):
        """После создания возвращаем данные пользователя без пароля."""
        return UserResponseSerializer(instance).data


class UserResponseSerializer(serializers.ModelSerializer):
    """
    Сериализатор для отображения данных пользователя после создания.
    Не включает чувствительные данные вроде пароля.
    """
    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'email')
        read_only_fields = fields  # Все поля только для чтения


class UserSerializer(serializers.ModelSerializer):
    """
    Основной сериализатор для модели User.
    Добавляет поле is_subscribed для проверки подписки.
    """
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('email', 'id', 'username', 'first_name',
                  'last_name', 'is_subscribed', 'avatar')
        read_only_fields = ('is_subscribed',)

    def get_is_subscribed(self, obj):
        """Проверяет, подписан ли текущий пользователь на просматриваемого."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Follow.objects.filter(user=request.user, author=obj).exists()
        return False

    def create(self, validated_data):
        """Создание пользователя."""
        return User.objects.create_user(**validated_data)


class UserAvatarSerializer(serializers.ModelSerializer):
    """
    Сериализатор для обновления аватара пользователя.
    Поддерживает загрузку изображений в формате base64.
    """
    avatar = Base64ImageField()

    class Meta:
        model = User
        fields = ('avatar',)
        extra_kwargs = {
            'avatar': {'required': True}
        }

    def update(self, instance, validated_data):
        """Обновление аватара пользователя."""
        instance.avatar = validated_data['avatar']
        instance.save()
        return instance


class FollowSerializer(serializers.ModelSerializer):
    """
    Сериализатор для подписок.
    Возвращает расширенные данные об авторе, включая его рецепты.
    """
    email = serializers.ReadOnlyField(source='author.email')
    id = serializers.ReadOnlyField(source='author.id')
    username = serializers.ReadOnlyField(source='author.username')
    first_name = serializers.ReadOnlyField(source='author.first_name')
    last_name = serializers.ReadOnlyField(source='author.last_name')
    is_subscribed = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()
    avatar = serializers.ImageField(source='author.avatar')

    class Meta:
        model = Follow
        fields = ('email', 'id', 'username', 'first_name',
                  'last_name', 'is_subscribed', 'avatar',
                  'recipes', 'recipes_count')

    def get_is_subscribed(self, obj):
        """Всегда True, так как это список подписок"""
        return True

    def get_recipes(self, obj):
        """Возвращает рецепты автора с возможностью ограничения количества."""
        from api.serializers import RecipeFollowSerializer
        request = self.context.get('request')
        recipes = obj.author.recipes.all()
        limit = request.query_params.get('recipes_limit') if request else None
        if limit and limit.isdigit():
            recipes = recipes[:int(limit)]
        return RecipeFollowSerializer(recipes, many=True,
                                      context={'request': request}).data

    def get_recipes_count(self, obj):
        """Возвращает общее количество рецептов автора."""
        return obj.author.recipes.count()

    def validate(self, data):
        """Проверяет возможность подписки."""
        author = self.context.get('author')
        user = self.context.get('request').user
        if Follow.objects.filter(
                author=author,
                user=user).exists():
            raise ValidationError(
                detail='Вы уже подписаны на этого пользователя!',
                code=status.HTTP_400_BAD_REQUEST)
        if user == author:
            raise ValidationError(
                detail='Невозможно подписаться на себя!',
                code=status.HTTP_400_BAD_REQUEST)
        return data
