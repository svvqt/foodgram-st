from base64 import b64decode
import re

from django.core.files.base import ContentFile
from rest_framework import serializers
from rest_framework.fields import CurrentUserDefault
from drf_extra_fields.fields import Base64ImageField
from djoser.serializers import UserSerializer as DjoserUserSerializer

from recipes.models import Ingredient, Recipe, RecipeIngredient, Favorite, ShoppingCart
from recipes.models import Follow
from users.models import User


class CustomUserSerializer(DjoserUserSerializer):
    """
    Основной сериализатор для модели User, наследуемый от Djoser.
    Добавляет поле is_subscribed для проверки подписки.
    """
    is_subscribed = serializers.SerializerMethodField()

    class Meta(DjoserUserSerializer.Meta):
        fields = DjoserUserSerializer.Meta.fields + ('is_subscribed', 'avatar')
        read_only_fields = ('is_subscribed',)

    def get_is_subscribed(self, obj):
        """Проверяет, подписан ли текущий пользователь на просматриваемого."""
        request = self.context.get('request')
        return (request and request.user.is_authenticated and 
                request.user.follower.filter(author=obj).exists())


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Ingredient. Возвращает основные данные об ингредиенте."""
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class AddIngredientSerializer(serializers.Serializer):
    """Сериализатор для добавления ингредиентов при создании рецепта."""
    id = serializers.IntegerField()
    amount = serializers.IntegerField(min_value=1)

    def validate_id(self, value):
        """Проверяет существование ингредиента."""
        if not Ingredient.objects.filter(id=value).exists():
            raise serializers.ValidationError('Ингредиент с указанным ID не существует')
        return value


class RecipeIngredientSerializer(serializers.ModelSerializer):
    """
    Сериализатор для связи рецепта и ингредиента (RecipeIngredient).
    Возвращает данные ингредиента с добавленным количеством для рецепта.
    """
    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit'
    )

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class BaseRecipeSerializer(serializers.ModelSerializer):
    """Базовый сериализатор для рецептов."""
    author = CustomUserSerializer(read_only=True)
    ingredients = RecipeIngredientSerializer(source='recipe_ingredients', many=True, read_only=True)
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    def _check_user_relation(self, obj, related_manager_name):
        """Проверяет отношение пользователя к рецепту."""
        request = self.context.get('request')
        return (request and request.user.is_authenticated and 
                getattr(obj, related_manager_name).filter(user=request.user).exists())

    def get_is_favorited(self, obj):
        return self._check_user_relation(obj, 'favorites')

    def get_is_in_shopping_cart(self, obj):
        return self._check_user_relation(obj, 'shoppingcarts')


class RecipeSerializer(BaseRecipeSerializer):
    """Сериализатор для чтения рецептов."""
    class Meta:
        model = Recipe
        fields = (
            'id', 'author', 'name', 'image', 'text',
            'ingredients', 'cooking_time', 'is_favorited',
            'is_in_shopping_cart'
        )


class RecipeCreateSerializer(BaseRecipeSerializer):
    """Сериализатор для создания и обновления рецептов."""
    ingredients = AddIngredientSerializer(many=True, write_only=True)
    image = serializers.CharField(required=True)
    author = serializers.HiddenField(default=CurrentUserDefault())

    class Meta:
        model = Recipe
        fields = (
            'ingredients', 'image', 'name', 'text',
            'cooking_time', 'author', 'is_favorited',
            'is_in_shopping_cart'
        )

    def validate(self, data):
        """Общая валидация данных рецепта."""
        if 'ingredients' not in data or not data['ingredients']:
            raise serializers.ValidationError(
                {'ingredients': ['Необходимо указать хотя бы один ингредиент']},
                code='required'
            )
        # Проверка на повторяющиеся ингредиенты
        ingredients = data['ingredients']
        ingredient_ids = [ingredient['id'] for ingredient in ingredients]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError(
                {'ingredients': ['Ингредиенты не должны повторяться']}
            )
        ingredient_serializer = AddIngredientSerializer(data=data['ingredients'], many=True)
        if not ingredient_serializer.is_valid():
            raise serializers.ValidationError(
                {'ingredients': ingredient_serializer.errors},
                code='invalid_ingredients'
            )
        if self.instance and self.instance.author != self.context['request'].user:
            raise serializers.ValidationError(
                {'detail': 'У вас нет прав для изменения этого рецепта'},
                code='permission_denied'
            )
        return data

    def validate_image(self, value):
        """Валидация изображения в формате base64."""
        try:
            format, imgstr = value.split(';base64,')
            ext = format.split('/')[-1]
            return ContentFile(b64decode(imgstr), name=f'temp.{ext}')
        except Exception:
            raise serializers.ValidationError('Некорректный формат изображения')

    def _create_recipe_ingredients(self, recipe, ingredients_data):
        """Создает связи между рецептом и ингредиентами."""
        RecipeIngredient.objects.bulk_create([
            RecipeIngredient(
                recipe=recipe,
                ingredient_id=ingredient['id'],
                amount=ingredient['amount']
            )
            for ingredient in ingredients_data
        ])

    def create(self, validated_data):
        """Создает рецепт с ингредиентами."""
        ingredients_data = validated_data.pop('ingredients')
        recipe = Recipe.objects.create(**validated_data)
        self._create_recipe_ingredients(recipe, ingredients_data)
        return recipe

    def update(self, instance, validated_data):
        """Обновляет рецепт и его ингредиенты."""
        ingredients_data = validated_data.pop('ingredients')
        instance.recipe_ingredients.all().delete()
        self._create_recipe_ingredients(instance, ingredients_data)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        """Возвращает данные рецепта после создания/обновления."""
        return RecipeSerializer(instance, context=self.context).data


class BaseRecipeActionSerializer(serializers.Serializer):
    """Базовый сериализатор для действий с рецептами (избранное/корзина)."""

    def to_representation(self, instance):
        """Формирует представление данных для ответа."""
        request = self.context.get('request')
        return {
            'id': instance.recipe.id,
            'name': instance.recipe.name,
            'image': request.build_absolute_uri(instance.recipe.image.url),
            'cooking_time': instance.recipe.cooking_time
        }


class FavoriteSerializer(BaseRecipeActionSerializer):
    """Сериализатор для избранных рецептов."""
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all())

    class Meta:
        model = Favorite
        fields = ('user', 'recipe')    
    
    def validate(self, data):
        """
        Проверяем, не добавлен ли уже рецепт в избранное
        """
        user = data.get('user')
        recipe = data.get('recipe')

        if Favorite.objects.filter(user=user, recipe=recipe).exists():
            raise serializers.ValidationError(
                {'detail': 'Этот рецепт уже есть в вашем избранном.'}
            )
        return data

    def create(self, validated_data):
        """Создаем запись в избранном"""
        return Favorite.objects.create(
            user=validated_data['user'],
            recipe=validated_data['recipe']
        )


class ShoppingCartSerializer(BaseRecipeActionSerializer):
    """Сериализатор для рецептов в корзине покупок."""
    def validate(self, data):
        """Проверяем валидность данных"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError({'detail': 'Требуется авторизация'})
        
        recipe = self.context.get('recipe')
        if not recipe or not isinstance(recipe, Recipe):
            raise serializers.ValidationError(
                {'recipe': 'Неверный тип рецепта. Ожидается объект Recipe.'}
            )
            
        if ShoppingCart.objects.filter(user=request.user, recipe=recipe).exists():
            raise serializers.ValidationError(
                {'detail': 'Этот рецепт уже добавлен в вашу корзину.'}
            )
        return data

    def create(self, validated_data):
        """Создаем запись в корзине покупок"""
        request = self.context['request']
        recipe = self.context['recipe']
        return ShoppingCart.objects.create(
            user=request.user,
            recipe=recipe
        )


class RecipeFollowSerializer(serializers.ModelSerializer):
    """Сериализатор для вывода рецептов в подписках (сокращенная версия)."""
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'cooking_time', 'image',)


# users


class UserCreateSerializer(DjoserUserSerializer):
    """
    Сериализатор для создания пользователя.
    Наследуется от Djoser с добавлением валидации username.
    """
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=True)

    class Meta(DjoserUserSerializer.Meta):
        fields = ('email', 'username', 'first_name', 'last_name', 'password')
        extra_kwargs = {'password': {'write_only': True}}

    def validate_username(self, value): 
        """Проверка уникальности username, длины и допустимых символов."""
        if not re.match(r'^[\w.@+-]+\Z', value):
            raise serializers.ValidationError(
                'Username может содержать только буквы, цифры и символы @/./+/-/_',
                code='invalid_username'
            )
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
        read_only_fields = fields


class UserAvatarSerializer(serializers.ModelSerializer):
    """
    Сериализатор для обновления аватара пользователя.
    Поддерживает загрузку изображений в формате base64.
    """
    avatar = Base64ImageField(required=True)

    class Meta:
        model = User
        fields = ('avatar',)


class BaseFollowSerializer(CustomUserSerializer):
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta:
        abstract = True

    def get_user_instance(self, obj):
        return obj.author if hasattr(obj, 'author') else obj

    def get_recipes(self, obj):
        user = self.get_user_instance(obj)
        request = self.context.get('request')
        recipes = user.recipes.all()
        limit = request.query_params.get('recipes_limit') if request else None
        
        if limit and limit.isdigit():
            recipes = recipes[:int(limit)]
        
        return RecipeFollowSerializer(recipes, many=True, context={'request': request}).data

    def get_recipes_count(self, obj):
        user = self.get_user_instance(obj)
        return user.recipes.count()
    
    def to_representation(self, instance):
        representation = super().to_representation(instance.author)
        representation.update({
            'recipes': self.get_recipes(instance),
            'recipes_count': self.get_recipes_count(instance),
            'is_subscribed': True
        })
        return representation


class FollowSerializer(BaseFollowSerializer):
    """Сериализатор для отображения подписок (GET-запросы)."""
    class Meta(CustomUserSerializer.Meta):
        fields = CustomUserSerializer.Meta.fields + ('recipes', 'recipes_count')


class SubscribeSerializer(serializers.ModelSerializer):
    """Сериализатор только для создания/удаления подписки (POST/DELETE)."""
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    author = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = Follow
        fields = ('user', 'author')

    def validate(self, data):
        author = data['author']
        user = data['user']

        if user == author:
            raise serializers.ValidationError(
                {'detail': 'Невозможно подписаться на себя!'},
                code='self_follow'
            )

        if Follow.objects.filter(author=author, user=user).exists():
            raise serializers.ValidationError(
                {'detail': 'Вы уже подписаны на этого пользователя!'},
                code='already_followed'
            )

        return data

    def to_representation(self, instance):
        """После создания возвращаем данные автора через FollowSerializer."""
        return FollowSerializer(instance, context=self.context).to_representation(instance)
