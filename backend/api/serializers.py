from rest_framework import serializers
from drf_extra_fields.fields import Base64ImageField
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.core.serializers.base import DeserializationError
from django.core.serializers.json import Serializer as JsonSerializer
from django.core.files.base import ContentFile
import base64

from recipes.models import (
    Ingredient, Recipe, RecipeIngredient,
    Favorite, ShoppingCart
)
from users.serializers import UserSerializer


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class AddIngredientSerializer(serializers.Serializer):
    """
    Serializer для поля ingredient модели Recipe - создание ингредиентов.
    """
    id = serializers.IntegerField()
    amount = serializers.IntegerField(min_value=1)


class RecipeIngredientSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit'
    )

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    ingredients = RecipeIngredientSerializer(
        source='recipe_ingredients',
        many=True,
        read_only=True
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'author', 'name', 'image', 'text',
            'ingredients', 'cooking_time', 'is_favorited',
            'is_in_shopping_cart'
        )

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Favorite.objects.filter(
                user=request.user,
                recipe=obj
            ).exists()
        return False

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return ShoppingCart.objects.filter(
                user=request.user,
                recipe=obj
            ).exists()
        return False


class RecipeCreateSerializer(serializers.ModelSerializer):
    ingredients = AddIngredientSerializer(
        many=True,
        write_only=True)
    image = serializers.CharField(required=True)  # Для base64
    author = serializers.HiddenField(
        default=serializers.CurrentUserDefault())
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'ingredients', 'image', 'name', 'text',
            'cooking_time', 'author', 'is_favorited',
            'is_in_shopping_cart'
        )
        extra_kwargs = {
            'image': {'required': True},
            'ingredients': {'required': True, 
                            'error_messages': {
                             'required': 'Необходимо указать хотя бы один ингредиент',
                             'null': 'Список ингредиентов не может быть пустым'
                            }
                            }
        }

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.in_favorites.filter(user=request.user).exists()
        return False

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.in_shopping_carts.filter(user=request.user).exists()
        return False

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError(
                'Необходимо указать ингредиенты'
            )
        
        if not value or len(value) < 1:
            raise serializers.ValidationError(
                {'ingredients': ['Должен быть указан хотя бы один ингредиент']},
                code='min_length'
            )
        
        # Проверка существования ингредиентов
        invalid_ingredients = []
        existing_ids = set(Ingredient.objects.filter(
            id__in=[item['id'] for item in value]
        ).values_list('id', flat=True))
        
        for ingredient_data in value:
            if ingredient_data['id'] not in existing_ids:
                invalid_ingredients.append(ingredient_data['id'])
        
        if invalid_ingredients:
            raise serializers.ValidationError(
                {'ingredients': [f'Ингредиенты с ID {invalid_ingredients} не существуют']},
                code='invalid'
            )

        # проверка повторяются ли ингредиенты
        ingredient_ids = [item['id'] for item in value]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError('Ингредиенты не должны повторяться')

        return value

    def validate(self, data):
        if 'image' not in data or not data['image']:
            raise serializers.ValidationError(
                {'image': ['Это поле обязательно.']},
                code='required'
            )
        return data

    def validate_image(self, value):
        if not value:
            raise serializers.ValidationError(
                'Поле image обязательно для заполнения'
            )

        try:
            format, imgstr = value.split(';base64,')
            ext = format.split('/')[-1]
            return ContentFile(base64.b64decode(imgstr), name=f'temp.{ext}')
        except Exception:
            raise serializers.ValidationError('Некорректный формат изображения')

    def create(self, validated_data):
        ingredients_data = validated_data.pop('ingredients')
        image_data = validated_data.pop('image', None)

        if image_data:
            validated_data['image'] = image_data

        recipe = Recipe.objects.create(**validated_data)

        # Remove the duplicate bulk_create and fix the ingredient access
        recipe_ingredients = []
        for ingredient_data in ingredients_data:
            # If ingredient_data is already an Ingredient object
            if isinstance(ingredient_data, Ingredient):
                ingredient = ingredient_data
                amount = ingredient_data.amount  # Assuming amount is stored in the object
            else:
                # If it's a dictionary (original expected behavior)
                ingredient = get_object_or_404(Ingredient, id=ingredient_data['id'])
                amount = ingredient_data['amount']

            recipe_ingredients.append(RecipeIngredient(
                recipe=recipe,
                ingredient=ingredient,
                amount=amount
            ))

        RecipeIngredient.objects.bulk_create(recipe_ingredients)
        return recipe

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('ingredients', None)
        if ingredients_data is not None:
            instance.recipe_ingredients.all().delete()
            for ingredient_data in ingredients_data:
                ingredient = get_object_or_404(
                    Ingredient,
                    id=ingredient_data['id']
                )
                RecipeIngredient.objects.create(
                    recipe=instance,
                    ingredient=ingredient,
                    amount=ingredient_data['amount']
                )

        try:
            # Обновляем ингредиенты
            if 'ingredients' in validated_data:
                instance.recipe_ingredients.all().delete()
                ingredients_data = validated_data.pop('ingredients')
                for ingredient_data in ingredients_data:
                    RecipeIngredient.objects.create(
                        recipe=instance,
                        ingredient_id=ingredient_data['id'],
                        amount=ingredient_data['amount']
                    )

            return super().update(instance, validated_data)
        except Exception as e:
            raise serializers.ValidationError(
                {'detail': str(e)},
                code='update_error'
            )

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        # Добавляем данные автора в ответ
        representation['author'] = {
            'id': instance.author.id,
            'username': instance.author.username,
            'first_name': instance.author.first_name,
            'last_name': instance.author.last_name,
            'email': instance.author.email,
            'is_subscribed': False,
            'avatar': instance.author.avatar.url if instance.author.avatar else None
        }

        # Добавляем ингредиенты в ответ
        representation['ingredients'] = [
            {
                'id': ri.ingredient.id,
                'name': ri.ingredient.name,
                'measurement_unit': ri.ingredient.measurement_unit,
                'amount': ri.amount
            }
            for ri in instance.recipe_ingredients.all()
        ]
        # Добавляем обязательные поля
        response_data = {
            'id': instance.id,
            'name': instance.name,
            'image': instance.image.url if instance.image else None,
            'text': instance.text,
            'cooking_time': instance.cooking_time,
            'author': representation['author'],
            'ingredients': representation['ingredients'],
            'is_favorited': self.get_is_favorited(instance),
            'is_in_shopping_cart': self.get_is_in_shopping_cart(instance)
        }
        return response_data


class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = ('user', 'recipe')

    def validate(self, data):
        if Favorite.objects.filter(
            user=data['user'],
            recipe=data['recipe']
        ).exists():
            raise serializers.ValidationError(
                'Рецепт уже в избранном'
            )
        return data


class ShoppingCartSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShoppingCart
        fields = ('user', 'recipe')

    def validate(self, data):
        if ShoppingCart.objects.filter(
            user=data['user'],
            recipe=data['recipe']
        ).exists():
            raise serializers.ValidationError(
                'Рецепт уже в списке покупок'
            )
        return data


class RecipeMiniSerializer(serializers.ModelSerializer):
    """Сериализатор предназначен для вывода рецептом в FollowSerializer."""
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'cooking_time', 'image',)
