from django.contrib import admin
from django import forms
from django.shortcuts import render, redirect
from django.urls import path
from django.http import HttpResponseRedirect
from django.contrib import messages
import logging
import json
from .models import Ingredient

from .models import (Favorite, Follow, Ingredient, IngredientRecipe,
                     Recipe, ShoppingCart,)

logger = logging.getLogger(__name__)


class IngredientsInline(admin.TabularInline):
    """
    Админ-зона для интеграции добавления ингридиентов в рецепты.
    Сразу доступно добавление 3х ингрдиентов.
    """
    model = IngredientRecipe
    extra = 3


class FollowAdmin(admin.ModelAdmin):
    """
    Админ-зона подписок.
    """
    list_display = ('user', 'author')
    list_filter = ('author',)
    search_fields = ('user',)


class FavoriteAdmin(admin.ModelAdmin):
    """
    Админ-зона избранных рецептов.
    """
    list_display = ('author', 'recipe')
    list_filter = ('author',)
    search_fields = ('author',)


class ShoppingCartAdmin(admin.ModelAdmin):
    """
    Админ-зона покупок.
    """
    list_display = ('author', 'recipe')
    list_filter = ('author',)
    search_fields = ('author',)


class IngredientRecipeAdmin(admin.ModelAdmin):
    """
    Админ-зона ингридентов для рецептов.
    """
    list_display = ('id', 'recipe', 'ingredient', 'amount',)
    list_filter = ('recipe', 'ingredient')
    search_fields = ('name',)


class RecipeAdmin(admin.ModelAdmin):
    """
    Админ-зона рецептов.
    Добавлен просмотр кол-ва добавленных рецептов в избранное.
    """
    list_display = ('id', 'author', 'name', 'pub_date', 'in_favorite', )
    search_fields = ('name',)
    list_filter = ('pub_date', 'author', 'name')
    filter_horizontal = ('ingredients',)
    empty_value_display = '-пусто-'
    inlines = [IngredientsInline]

    def in_favorite(self, obj):
        return obj.favorite.all().count()

    in_favorite.short_description = 'Добавленные рецепты в избранное'


class TagAdmin(admin.ModelAdmin):
    """
    Админ-зона тегов.
    """
    list_display = ('id', 'name', 'slug', 'color')
    list_filter = ('name',)
    search_fields = ('name',)


# class IngredientAdmin(admin.ModelAdmin):
#    """
#    Админ-зона ингридиентов.
#    """
#    list_display = ('name', 'measurement_unit')
#    list_filter = ('name',)
#    search_fields = ('name',)


class JsonUploadForm(forms.Form):
    """Форма для загрузки JSON файла"""
    json_file = forms.FileField(label='JSON файл с ингредиентами')


class IngredientAdmin(admin.ModelAdmin):
    """
    Админ-зона ингредиентов с возможностью загрузки из JSON.
    """
    list_display = ('name', 'measurement_unit')
    list_filter = ('name',)
    search_fields = ('name',)
    change_form_template = 'admin/ingredient_change_form.html'   # Кастомный шаблон
    change_list_template = 'admin/ingredients_change_list.html'  # Кастомный шаблон
    
    def get_urls(self):
        """Добавляем кастомный URL для загрузки JSON"""
        urls = super().get_urls()
        custom_urls = [
            path('upload-json/', self.upload_json, name='upload_json'),
        ]
        return custom_urls + urls
    
    def upload_json(self, request):
        logger.warning("upload_json view called")
        try:
            if request.method == 'POST':
                form = JsonUploadForm(request.POST, request.FILES)
                if form.is_valid():
                    json_file = request.FILES['json_file']
                    data = json.loads(json_file.read().decode('utf-8'))
                    created_count = 0
                    updated_count = 0
                    for item in data:
                        obj, created = Ingredient.objects.update_or_create(
                            name=item['name'],
                            defaults={'measurement_unit': item['measurement_unit']}
                        )
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1
                    messages.success(request, f"Успешно загружено! Создано: {created_count}, Обновлено: {updated_count}")
                    return HttpResponseRedirect("../")
            else:
                form = JsonUploadForm()
            context = self.admin_site.each_context(request)
            context.update({
                'form': form,
                'title': 'Загрузка ингредиентов из JSON',
                'opts': self.model._meta,
            })
            return render(request, 'admin/json_upload.html', context)
        except Exception as e:
            logger.error(f"Error in upload_json: {e}", exc_info=True)
            messages.error(request, f"Ошибка загрузки: {str(e)}")
            return HttpResponseRedirect("../")


admin.site.register(Recipe, RecipeAdmin)
admin.site.register(Ingredient, IngredientAdmin)
admin.site.register(IngredientRecipe, IngredientRecipeAdmin)
admin.site.register(Follow, FollowAdmin)
admin.site.register(Favorite, FavoriteAdmin)
admin.site.register(ShoppingCart, ShoppingCartAdmin)
