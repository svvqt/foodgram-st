from datetime import datetime
import io
from pathlib import Path
import logging

from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont, TTFError
from django.conf import settings
from django.http import HttpResponse
from django.db.models import Sum

from recipes.models import RecipeIngredient, ShoppingCart

logger = logging.getLogger(__name__)


def shopping_cart_pdf(request):
    """Создание PDF со списком продуктов для выбранных рецептов пользователя."""

    # Настройка шрифтов
    FONT_DIR = Path(settings.BASE_DIR) / "fonts"
    FONT_PATHS = {
        'DejaVuSans': FONT_DIR / "DejaVuSans.ttf",
        'DejaVuSans-Bold': FONT_DIR / "DejaVuSans-Bold.ttf",
        'DejaVuSans-Oblique': FONT_DIR / "DejaVuSans-Oblique.ttf",
    }

    # Создаем PDF буфер
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)

    try:
        # Регистрация шрифтов с fallback
        fonts_registered = {}
        for font_name, font_path in FONT_PATHS.items():
            try:
                if font_path.exists():
                    pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
                    fonts_registered[font_name] = True
                else:
                    logger.warning(f"Файл шрифта {font_name} не найден: {font_path}")
                    fonts_registered[font_name] = False
            except TTFError as e:
                logger.warning(f"Ошибка загрузки шрифта {font_name}: {e}")
                fonts_registered[font_name] = False

        # Установка fallback шрифтов
        fallback_fonts = {
            'DejaVuSans': 'Helvetica',
            'DejaVuSans-Bold': 'Helvetica-Bold',
            'DejaVuSans-Oblique': 'Helvetica-Oblique'
        }
        user = request.user
        shopping_carts = ShoppingCart.objects.filter(user=user)
        recipe_ids = [cart.recipe.id for cart in shopping_carts]

        ingredients = RecipeIngredient.objects.filter(
            recipe_id__in=recipe_ids
        ).values(
            'ingredient__name',
            'ingredient__measurement_unit'
        ).annotate(
            total_amount=Sum('amount')
        ).order_by('ingredient__name')

        # Заголовок
        title_font = 'DejaVuSans-Bold' if fonts_registered.get('DejaVuSans-Bold', False) else fallback_fonts['DejaVuSans-Bold']
        pdf.setFont(title_font, 16)
        pdf.drawCentredString(300, 750, "Ваш список покупок")

        # Таблица с ингредиентами
        data = [["Ингредиент", "Количество", "Ед. измерения"]]
        for item in ingredients:
            data.append([
                item['ingredient__name'],
                str(item['total_amount']),
                item['ingredient__measurement_unit']
            ])

        # Стили таблицы
        table_font = 'DejaVuSans' if fonts_registered.get('DejaVuSans', False) else fallback_fonts['DejaVuSans']
        table_font_bold = 'DejaVuSans-Bold' if fonts_registered.get('DejaVuSans-Bold', False) else fallback_fonts['DejaVuSans-Bold']

        table = Table(data, colWidths=[250, 100, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), table_font_bold),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), table_font),
        ]))

        table.wrapOn(pdf, 0, 0)
        table.drawOn(pdf, 50, 650)

        # Дата создания
        date_font = 'DejaVuSans-Oblique' if fonts_registered.get('DejaVuSans-Oblique', False) else fallback_fonts['DejaVuSans-Oblique']
        pdf.setFont(date_font, 10)
        pdf.drawString(50, 50, f"Создано: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        pdf.showPage()
        pdf.save()

        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="shopping_list.pdf"'
        return response

    except Exception as e:
        logger.error(f"Ошибка при создании PDF: {e}", exc_info=True)
        return HttpResponse(
            "Произошла ошибка при генерации PDF",
            status=500,
            content_type='text/plain'
        )
