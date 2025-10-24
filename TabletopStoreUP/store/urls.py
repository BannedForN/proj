from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views
from . import admin_reports

app_name = 'store'

urlpatterns = [
    # Список продуктов (класс ProductListView)
    path('', views.ProductListView.as_view(), name='product_list'),

    # Детали продукта (DetailView)
    path('product/<int:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('product/<int:product_id>/review/', views.add_review, name='add_review'),

    # Корзина
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:item_id>/', views.cart_remove, name='cart_remove'),

    # Заказы
    path('order/create/', views.order_create, name='create_order'),
    path('order/success/<int:order_id>/', views.order_success_view, name='order_success'),

    # Пользователи
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

path('password_reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='store/password_reset_form.html',
             email_template_name='store/password_reset_email.html',
             success_url=reverse_lazy('store:password_reset_done')
         ), 
         name='password_reset'),

    path('password_reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='store/password_reset_done.html'
         ),
         name='password_reset_done'),

    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='store/password_reset_confirm.html',
             success_url=reverse_lazy('store:password_reset_complete')
         ),
         name='password_reset_confirm'),

    path('reset/done/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='store/password_reset_complete.html'
         ),
         name='password_reset_complete'),

    path('orders/', views.order_list, name='order_list'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('api/user/toggle-theme/', views.toggle_theme, name='toggle_theme'),
]
