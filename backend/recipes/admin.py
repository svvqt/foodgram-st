import json
import logging

from django.contrib import admin
from django import forms
from django.shortcuts import render
from django.urls import path
from django.http import HttpResponseRedirect

from recipes.models import (
    Ingredient, Recipe, RecipeIngredient,
    Favorite, ShoppingCart
)

logger = logging.getLogger(__name__)


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1
    min_num = 1


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'name', 'author',
        'cooking_time', 'pub_date',
        'favorites_count'
    )
    list_filter = ('author', 'name', 'pub_date')
    search_fields = ('name', 'author__username')
    inlines = (RecipeIngredientInline,)

    @admin.display(description='В избранном')
    def favorites_count(self, obj):
        return obj.in_favorites.count()


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'measurement_unit')
    list_filter = ('name',)
    search_fields = ('name',)


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'recipe')
    list_filter = ('user',)
    search_fields = ('user__username', 'recipe__name')


@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'recipe')
    list_filter = ('user',)
    search_fields = ('user__username', 'recipe__name')


class JsonUploadForm(forms.Form):
    json_file = forms.FileField(label='JSON файл с ингредиентами')


@admin.register(RecipeIngredient)
class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = ('id', 'recipe', 'ingredient', 'amount')
    list_filter = ('recipe', 'ingredient')
    search_fields = ('recipe__name', 'ingredient__name')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-json/', self.upload_json, name='upload_json'),
        ]
        return custom_urls + urls

    def upload_json(self, request):
        if request.method == 'POST':
            form = JsonUploadForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    json_file = request.FILES['json_file']
                    data = json.loads(json_file.read().decode('utf-8'))
                    created = 0
                    for item in data:
                        Ingredient.objects.get_or_create(
                            name=item['name'],
                            measurement_unit=item['measurement_unit']
                        )
                        created += 1
                    self.message_user(
                        request,
                        f'Успешно загружено {created} ингредиентов'
                    )
                except Exception as e:
                    logger.error(f'Ошибка загрузки JSON: {e}')
                    self.message_user(
                        request,
                        f'Ошибка загрузки: {e}',
                        level='error'
                    )
                return HttpResponseRedirect("../")
        else:
            form = JsonUploadForm()

        context = {
            'form': form,
            'title': 'Загрузка ингредиентов из JSON',
            'opts': self.model._meta,
        }
        return render(request, 'admin/json_upload.html', context)
