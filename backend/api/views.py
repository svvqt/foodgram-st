from rest_framework.response import Response
from django.http import HttpResponse
from django.db.models import Sum
from rest_framework import (
    viewsets, status, permissions
)
import io
from datetime import datetime
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.conf import settings
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.urls import reverse
from .paginations import StandardResultsSetPagination
from rest_framework.exceptions import PermissionDenied
from recipes.models import (Recipe, Ingredient,
                            Favorite, ShoppingCart, RecipeIngredient)
from .serializers import (
    IngredientSerializer, RecipeSerializer,
    RecipeCreateSerializer, FavoriteSerializer,
    ShoppingCartSerializer
)
from api.permissions import IsAuthorOrAdminOrReadOnly


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = None

    def get_queryset(self):
        name = self.request.query_params.get('name')
        if name:
            return self.queryset.filter(name__istartswith=name)
        return self.queryset


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    pagination_class = StandardResultsSetPagination
    permission_classes = (IsAuthorOrAdminOrReadOnly,)

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return RecipeCreateSerializer
        return RecipeSerializer

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if instance.author != request.user and not request.user.is_staff:
                raise PermissionDenied(
                    {"detail": "У вас нет прав изменять этот рецепт."}
                )
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.pop('partial', False))
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data)
        except PermissionDenied:
            return Response(
                {"detail": "У вас нет прав изменять этот рецепт."},
                status=status.HTTP_403_FORBIDDEN
            )

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        is_favorited = self.request.query_params.get('is_favorited')
        if is_favorited == '1' and user.is_authenticated:
            queryset = queryset.filter(in_favorites__user=user)

        is_in_shopping_cart = self.request.query_params.get(
            'is_in_shopping_cart'
        )
        if is_in_shopping_cart == '1' and user.is_authenticated:
            queryset = queryset.filter(in_shopping_carts__user=user)

        author_id = self.request.query_params.get('author')
        if author_id:
            queryset = queryset.filter(author_id=author_id)

        return queryset

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def favorite(self, request, pk=None):
        recipe = self.get_object()
        user = request.user
        favorite_model = Favorite

        if request.method == 'POST':
            # Проверяем, не добавлен ли уже рецепт
            if favorite_model.objects.filter(user=user, recipe=recipe).exists():
                return Response(
                    {'detail': 'Этот рецепт уже есть в вашем избранном.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Создаем запись в избранном
            favorite = favorite_model.objects.create(user=user, recipe=recipe)
            serializer = FavoriteSerializer(
                favorite, 
                context={'request': request}
            )
            return Response(
                serializer.data, 
                status=status.HTTP_201_CREATED
            )

        elif request.method == 'DELETE':
            # Удаляем рецепт из избранного, если он там есть
            deleted_count, _ = favorite_model.objects.filter(
                user=user,
                recipe=recipe
            ).delete()

            if deleted_count == 0:
                return Response(
                    {'detail': 'Рецепт не был найден в избранном.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response(
                {'detail': 'Рецепт успешно удален из избранного.'},
                status=status.HTTP_204_NO_CONTENT
            )

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def shopping_cart(self, request, pk=None):
        recipe = get_object_or_404(Recipe, pk=pk)
        user = request.user
        cart_model = ShoppingCart

        if request.method == 'POST':
            # Проверяем, есть ли рецепт уже в корзине
            if cart_model.objects.filter(user=user, recipe=recipe).exists():
                return Response(
                    {'message': 'Этот рецепт уже добавлен в вашу корзину.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
            # Создаем запись в корзине
            cart_item = cart_model(user=user, recipe=recipe)
            cart_item.save()
        
            serializer = ShoppingCartSerializer(cart_item, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        elif request.method == 'DELETE':
            # Пытаемся найти и удалить рецепт из корзины
            cart_item = cart_model.objects.filter(user=user, recipe=recipe).first()
        
            if not cart_item:
                return Response(
                    {'message': 'Этот рецепт не найден в вашей корзине.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
            cart_item.delete()
            return Response(
                {'message': 'Рецепт успешно удален из корзины.'},
                status=status.HTTP_204_NO_CONTENT
            )

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def download_shopping_cart(self, request):
        # Регистрируем шрифты с поддержкой кириллицы
        font_path = Path(settings.BASE_DIR) / "static/fonts/DejaVuSans.ttf"
        font_bold_path = Path(settings.BASE_DIR) / "static/fonts/DejaVuSans-Bold.ttf"
        
        pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', font_bold_path))

        # Получаем ингредиенты
        ingredients = RecipeIngredient.objects.filter(
            recipe__in_shopping_carts__user=request.user
        ).values(
            'ingredient__name',
            'ingredient__measurement_unit'
        ).annotate(total_amount=Sum('amount')).order_by('ingredient__name')

        # Создаем PDF
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)

        # Заголовок (используем DejaVuSans-Bold)
        pdf.setFont("DejaVuSans-Bold", 16)
        pdf.drawCentredString(300, 750, "Ваш список покупок")

        # Имя пользователя (обычный шрифт)
        pdf.setFont("DejaVuSans", 12)
        user_name = request.user.get_full_name() or request.user.username
        pdf.drawString(50, 730, f"Пользователь: {user_name}")

        # Таблица с ингредиентами
        data = [["Ингредиент", "Количество", "Ед. измерения"]]
        for item in ingredients:
            data.append([
                item['ingredient__name'],
                str(item['total_amount']),
                item['ingredient__measurement_unit']
            ])

        table = Table(data, colWidths=[250, 100, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'DejaVuSans-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'DejaVuSans'),
        ]))

        table.wrapOn(pdf, 0, 0)
        table.drawOn(pdf, 50, 650)

        # Дата создания
        pdf.setFont("DejaVuSans-Oblique", 10)
        pdf.drawString(50, 50, f"Создано: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        pdf.showPage()
        pdf.save()

        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="shopping_list.pdf"'
        return response

    @action(detail=True, methods=['get'], url_path='get-link')
    def get_recipe_link(self, request, pk=None):
        """Генерирует полную ссылку на рецепт."""
        recipe = self.get_object()
        absolute_url = request.build_absolute_uri(
            reverse('recipes-detail', kwargs={'pk': recipe.id}))
        return Response({'short-link': absolute_url})
