from django.contrib import admin
from django.urls import path
from . import admin_reports
from .models import (
    UserRole, UserProfile, Genre, PlayerRange, Product,
    OrderStatus, Order, OrderItem, PaymentStatus, Payment,
    DeliveryMethod, DeliveryStatus, Delivery, Review
)

# ===== Регистрация моделей =====

admin.site.register(UserRole)
admin.site.register(UserProfile)
admin.site.register(Genre)
admin.site.register(PlayerRange)
admin.site.register(OrderStatus)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(PaymentStatus)
admin.site.register(Payment)
admin.site.register(DeliveryMethod)
admin.site.register(DeliveryStatus)
admin.site.register(Delivery)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('product__name', 'user__username', 'comment')
    readonly_fields = ('created_at',)


class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0
    readonly_fields = ('user', 'rating', 'comment', 'created_at')
    can_delete = True


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'stock')
    inlines = [ReviewInline]


# ===== Настройки заголовков =====

admin.site.index_title = "Панель управления магазином"
admin.site.site_header = "Админ-панель магазина игр"
admin.site.site_title = "Магазин игр"

# ===== Кастомная страница аналитики в админке =====

from django.urls import re_path
from django.utils.html import format_html

def get_custom_admin_urls(original_get_urls):
    def custom_urls():
        urls = original_get_urls()
        my_urls = [
            re_path(r'^analytics/$', admin_reports.analytics_dashboard, name='admin_analytics'),
            re_path(r'^analytics/export/$', admin_reports.export_analytics_csv, name='export_analytics_csv'),
        ]
        return my_urls + urls
    return custom_urls

admin.site.get_urls = get_custom_admin_urls(admin.site.get_urls)

# Добавим кнопку "Аналитика" на главную страницу админки
admin.site.index_title = format_html('Панель управления магазином | <a href="/admin/analytics/" style="color:#007bff;">📊 Аналитика</a>')