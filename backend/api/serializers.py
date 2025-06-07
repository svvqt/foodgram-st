from base64 import b64decode

from drf_extra_fields.fields import Base64ImageField
from django.core.files.base import ContentFile
from rest_framework.fields import CurrentUserDefault
from djoser.serializers import UserSerializer as DjoserUserSerializer
from rest_framework import serializers

from recipes.models import Ingredient, Recipe, RecipeIngredient, Favorite, ShoppingCart
from recipes.models import Follow
from users.models import User


class CustomUserSerializer(DjoserUserSerializer):
    """Основной сериализатор для модели User.

    Наследуется от Djoser.
    Добавляет поле is_subscribed для проверки подписки.
    """

    is_subscribed = serializers.SerializerMethodField()

    class Meta(DjoserUserSerializer.Meta):
        fields = DjoserUserSerializer.Meta.fields + (
            'is_subscribed',
            'avatar',
        )

    def get_is_subscribed(self, obj):
        """Проверяет, подписан ли текущий пользователь на просматриваемого."""

        request = self.context.get('request')
        return (request and request.user.is_authenticated and 
                request.user.follower.filter(author=obj).exists())


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Ingredient.

    Возвращает основные данные об ингредиенте.
    """

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
    """Сериализатор для связи рецепта и ингредиента (RecipeIngredient).

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

    def _check_user_relation(self, obj, relation_manager):
        """Проверяет отношение пользователя к рецепту."""

        request = self.context.get('request')
        return (request and
                request.user.is_authenticated and
                relation_manager.filter(user=request.user).exists())

    def get_is_favorited(self, obj):
        return self._check_user_relation(obj, obj.favorites)

    def get_is_in_shopping_cart(self, obj):
        return self._check_user_relation(obj, obj.shoppingcarts)


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

        RecipeIngredient.objects.bulk_create(
            RecipeIngredient(
                recipe=recipe,
                ingredient_id=ingredient['id'],
                amount=ingredient['amount']
            )
            for ingredient in ingredients_data
        )

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


class BaseRecipeActionSerializer(serializers.ModelSerializer):
    """Базовый сериализатор для действий с рецептами (избранное/корзина)."""

    def validate(self, data):
        if self.Meta.model.objects.filter(**data).exists():
            raise serializers.ValidationError(self.error_message)
        return data

    def to_representation(self, instance): 
        """Формирует представление данных для ответа."""

        return RecipeFollowSerializer(instance.recipe, context=self.context).data


class FavoriteSerializer(BaseRecipeActionSerializer):
    """Сериализатор для избранных рецептов."""

    error_message = 'Этот рецепт уже есть в вашем избранном.'

    class Meta:
        model = Favorite
        fields = ('user', 'recipe')


class ShoppingCartSerializer(BaseRecipeActionSerializer):
    """Сериализатор для рецептов в корзине покупок."""

    error_message = 'Рецепт уже в корзине.'

    class Meta:
        model = ShoppingCart
        fields = ('user', 'recipe')


class RecipeFollowSerializer(serializers.ModelSerializer):
    """Сериализатор для вывода рецептов в подписках."""

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'cooking_time', 'image',)


# users


class UserResponseSerializer(serializers.ModelSerializer): 
    """Сериализатор для отображения данных пользователя после создания.

    Не включает чувствительные данные вроде пароля.
    """

    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'email')
        read_only_fields = fields


class UserAvatarSerializer(serializers.ModelSerializer):
    """Сериализатор для обновления аватара пользователя.

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

    def get_recipes(self, obj):
        request = self.context.get('request')
        recipes = obj.recipes.all()
        limit = request.query_params.get('recipes_limit') if request else None

        if limit and limit.isdigit():
            recipes = recipes[:int(limit)]

        return RecipeFollowSerializer(recipes, many=True, context={'request': request}).data

    def get_recipes_count(self, obj):
        return obj.recipes.count()


class FollowSerializer(BaseFollowSerializer):
    """Сериализатор для отображения подписок (GET-запросы)."""

    class Meta(CustomUserSerializer.Meta):
        fields = CustomUserSerializer.Meta.fields + ('recipes', 'recipes_count')


class SubscribeSerializer(serializers.ModelSerializer):
    """Сериализатор только для создания/удаления подписки (POST/DELETE)."""

    class Meta:
        model = Follow
        fields = ('user', 'author')

    def validate(self, data):
        author = data.get('author')
        user = data.get('user')

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

        request = self.context.get('request')
        return FollowSerializer(instance.author, context={'request': request}).data
