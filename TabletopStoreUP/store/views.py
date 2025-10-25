from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Avg, Sum, Count, Q, Subquery, OuterRef, FloatField, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseRedirect, FileResponse
from django.utils.http import urlencode
from django.contrib import messages
from django.db import transaction
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.views.generic import ListView, DetailView
from .forms import UserSettingsForm
import os
from django.conf import settings

from rest_framework import viewsets, status, generics, permissions
from rest_framework.response import Response
from rest_framework.decorators import action

from .models import (
    UserRole, OrderStatus, PaymentStatus, DeliveryMethod, DeliveryStatus,
    Genre, PlayerRange, Product, Order, OrderItem, Payment, Delivery,
    UserProfile, Cart, CartItem, Review, UserSettings, PaymentMethod
)
from .serializers import (
    UserRoleSerializer, OrderStatusSerializer, PaymentStatusSerializer,
    DeliveryMethodSerializer, DeliveryStatusSerializer, GenreSerializer,
    PlayerRangeSerializer, UserSerializer, ProductSerializer,
    OrderItemSerializer, OrderSerializer, PaymentSerializer,
    DeliverySerializer, UserProfileSerializer, RegisterSerializer
)
from .permissions import IsAdmin, IsManagerOrAdmin, IsClientOrReadOnly
from .forms import RegisterForm, LoginForm, ReviewForm, OrderCreateForm, CheckoutForm
import csv
from django.contrib.admin.views.decorators import staff_member_required


User = get_user_model()


# -------------------------
# REST API ViewSets
# -------------------------
class UserRoleViewSet(viewsets.ModelViewSet):
    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer

class OrderStatusViewSet(viewsets.ModelViewSet):
    queryset = OrderStatus.objects.all()
    serializer_class = OrderStatusSerializer

class PaymentStatusViewSet(viewsets.ModelViewSet):
    queryset = PaymentStatus.objects.all()
    serializer_class = PaymentStatusSerializer

class DeliveryMethodViewSet(viewsets.ModelViewSet):
    queryset = DeliveryMethod.objects.all()
    serializer_class = DeliveryMethodSerializer

class DeliveryStatusViewSet(viewsets.ModelViewSet):
    queryset = DeliveryStatus.objects.all()
    serializer_class = DeliveryStatusSerializer

class GenreViewSet(viewsets.ModelViewSet):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer

class PlayerRangeViewSet(viewsets.ModelViewSet):
    queryset = PlayerRange.objects.all()
    serializer_class = PlayerRangeSerializer

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return [permissions.AllowAny()]

class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsManagerOrAdmin() if self.request.user.is_staff else permissions.IsAuthenticated()]
        if self.action == 'create':
            return [IsClientOrReadOnly()]
        return [IsManagerOrAdmin()]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Создание заказа через API с проверкой stock
        """
        try:
            order_data = request.data.copy()
            items_data = order_data.pop("items", [])
            payment_data = order_data.pop("payment", None)

            order_serializer = self.get_serializer(data=order_data)
            order_serializer.is_valid(raise_exception=True)
            order = order_serializer.save(user=request.user)

            total = 0
            for item_data in items_data:
                product = Product.objects.get(pk=item_data["product"])
                if product.stock < item_data["quantity"]:
                    raise ValueError(f"Недостаточно товара на складе: {product.name}")
                product.stock -= item_data["quantity"]
                product.save()

                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=item_data["quantity"]
                )
                total += product.price * item_data["quantity"]

            if payment_data:
                Payment.objects.create(
                    order=order,
                    amount=total,
                    status=PaymentStatus.objects.get_or_create(name="Pending")[0]
                )

            order.total = total
            order.save()
            return Response(self.get_serializer(order).data, status=status.HTTP_201_CREATED)

        except Exception as e:
            transaction.set_rollback(True)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Удаление заказа и возврат stock
        """
        order = self.get_object()
        try:
            for item in order.items.all():
                product = item.product
                product.stock += item.quantity
                product.save()
            order.delete()
            return Response({"detail": "Заказ удалён и товары возвращены на склад."}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            transaction.set_rollback(True)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer

class DeliveryViewSet(viewsets.ModelViewSet):
    queryset = Delivery.objects.all()
    serializer_class = DeliverySerializer

class UserProfileViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserProfile.objects.select_related('user', 'role')
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


# -------------------------
# Django Views
# -------------------------
class ProductListView(ListView):
    model = Product
    template_name = 'store/product_list.html'
    context_object_name = 'products'
    paginate_by = 12

    def get_queryset(self):
        # Подсчёт популярности
        base = (Product.objects
                .select_related('genre')
                .prefetch_related('player_ranges')
                .annotate(orderitems_count=Count('orderitem', distinct=True))
                )

        avg_subq = (Review.objects
                    .filter(product_id=OuterRef('pk'))
                    .values('product_id')
                    .annotate(a=Count('id') * 0.0)
                    )

        from django.db.models import Avg
        avg_subq = (Review.objects
                    .filter(product_id=OuterRef('pk'))
                    .values('product_id')
                    .annotate(a=Avg('rating'))
                    .values('a')[:1])

        qs = base.annotate(
            avg_rating=Coalesce(
                Subquery(avg_subq, output_field=FloatField()),
                Value(0.0)
            )
        )

        params = self.request.GET

        # --- Поиск ---
        q = (params.get('q') or '').strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

        # --- Фильтры ---
        genre_id = params.get('genre')
        if genre_id:
            qs = qs.filter(genre_id=genre_id)

        in_stock = params.get('in_stock')
        if in_stock == '1':
            qs = qs.filter(stock__gt=0)

        price_min = params.get('price_min')
        if price_min:
            qs = qs.filter(price__gte=price_min)

        price_max = params.get('price_max')
        if price_max:
            qs = qs.filter(price__lte=price_max)

        rating_min = params.get('rating_min')
        if rating_min:
            qs = qs.filter(avg_rating__gte=rating_min)

        players = params.getlist('players')
        if players:
            qs = qs.filter(player_ranges__in=players).distinct()

        # --- Сортировка ---
        sort = params.get('sort') or 'new'
        sort_map = {
            'price_asc': 'price',
            'price_desc': '-price',
            'rating_desc': '-avg_rating',
            'rating_asc': 'avg_rating',
            'popular': '-orderitems_count',
            'new': '-id',
        }
        qs = qs.order_by(sort_map.get(sort, '-id'))

        return qs
    
    def get_paginate_by(self, queryset):
        if self.request.user.is_authenticated and hasattr(self.request.user, 'settings'):
            try:
                return int(self.request.user.settings.page_size or self.paginate_by)
            except Exception:
                return self.paginate_by
        return self.paginate_by

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()

        def _page_url(page):
            params2 = params.copy()
            params2['page'] = page
            return f"{self.request.path}?{urlencode(params2)}"

        page_obj = ctx.get('page_obj')
        ctx['next_page_url'] = _page_url(page_obj.next_page_number()) if page_obj and page_obj.has_next() else ''
        ctx['prev_page_url'] = _page_url(page_obj.previous_page_number()) if page_obj and page_obj.has_previous() else ''

        ctx['genres'] = Genre.objects.all().order_by('name')
        ctx['player_ranges'] = PlayerRange.objects.all().order_by('min_players', 'max_players')

        ctx['current'] = {
            'q': self.request.GET.get('q', ''),
            'genre': self.request.GET.get('genre', ''),
            'in_stock': self.request.GET.get('in_stock', ''),
            'price_min': self.request.GET.get('price_min', ''),
            'price_max': self.request.GET.get('price_max', ''),
            'rating_min': self.request.GET.get('rating_min', ''),
            'players': self.request.GET.getlist('players'),
            'sort': self.request.GET.get('sort', 'new'),
        }

        ctx['has_active_filters'] = any([
            ctx['current']['genre'], ctx['current']['in_stock'],
            ctx['current']['price_min'], ctx['current']['price_max'],
            ctx['current']['rating_min'], ctx['current']['players']
        ])

        ctx['save_filters_url'] = reverse('store:save_catalog_filters')
        ctx['apply_filters_url'] = reverse('store:apply_catalog_filters')

        ctx['page_sizes'] = [8, 12, 16, 24, 32, 48]

        ctx['reset_url'] = self.request.path
        return ctx


class ProductDetailView(DetailView):
    model = Product
    template_name = 'store/product_detail.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        reviews = product.reviews.all()
        avg_rating = reviews.aggregate(average=Avg('rating'))['average'] or 0
        context['reviews'] = reviews
        context['avg_rating'] = avg_rating
        return context

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.full_name = form.cleaned_data.get('full_name') or user.username
                profile.phone = form.cleaned_data.get('phone') or ''
                profile.save(update_fields=['full_name', 'phone'])
            login(request, user)
            messages.success(request, "Регистрация успешна!")
            return redirect('store:product_list')
    else:
        form = RegisterForm()
    return render(request, 'store/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, "Вы вошли в систему.")
            return redirect('store:product_list')
        else:
            messages.error(request, "Неправильный логин или пароль.")
    else:
        form = LoginForm()
    return render(request, 'store/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('store:product_list')

@login_required
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    reviews = product.reviews.all()
    avg_rating = reviews.aggregate(average=Avg('rating'))['average'] or 0

    context = {
        'product': product,
        'reviews': reviews,
        'avg_rating': avg_rating
    }
    return render(request, 'store/product_detail.html', context)

@login_required
def cart_detail(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('product')
    total = sum(item.product.price * item.quantity for item in items)
    return render(request, 'store/cart_detail.html', {'cart': cart, 'items': items, 'total': total})


@login_required
def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart, _ = Cart.objects.get_or_create(user=request.user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)

    if not created:
        item.quantity += 1

    item.save()
    messages.success(request, f'{product.name} добавлен в корзину.')
    return redirect('store:cart_detail')


@login_required
def cart_remove(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    
    if item.quantity > 1:
        item.quantity -= 1
        item.save()
        messages.info(request, f'Количество {item.product.name} уменьшено на 1.')
    else:
        item.delete()
        messages.info(request, f'{item.product.name} удалён из корзины.')

    return redirect('store:cart_detail')

@login_required
def order_create(request):
    cart = get_object_or_404(Cart, user=request.user)
    items = cart.items.select_related('product')

    if not items.exists():
        messages.error(request, "Ваша корзина пуста.")
        return redirect('store:product_list')

    total = sum(i.product.price * i.quantity for i in items)

    if request.method == 'POST':
        form = OrderCreateForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Проверьте форму.")
            return render(request, 'store/order_create.html', {'cart': cart, 'form': form, 'total': total})

        address = form.cleaned_data['address']
        method: PaymentMethod = form.cleaned_data['payment_method']

        with transaction.atomic():
            status_new, _ = OrderStatus.objects.get_or_create(name="New")
            order = Order.objects.create(
                user=request.user,
                status=status_new,
                total=total
            )

            for item in items:
                if item.product.stock < item.quantity:
                    messages.error(request, f"Недостаточно товара: {item.product.name}")
                    raise transaction.TransactionManagementError("Out of stock")

                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )
                item.product.stock -= item.quantity
                item.product.save(update_fields=['stock'])

            delivery_status, _ = DeliveryStatus.objects.get_or_create(name="Pending")
            delivery_method, _ = DeliveryMethod.objects.get_or_create(name="Standard")
            Delivery.objects.create(
                order=order,
                address=address,
                method=delivery_method,
                status=delivery_status
            )

            p_status_pending, _ = PaymentStatus.objects.get_or_create(name="Pending")
            payment = Payment.objects.create(
                order=order,
                amount=order.total,
                status=p_status_pending,
                method=method
            )


            if method.code == 'cod':
                p_status, _ = PaymentStatus.objects.get_or_create(name="Authorized")
                order_paid, _ = OrderStatus.objects.get_or_create(name="Awaiting Shipment")
                payment.status = p_status
                payment.save(update_fields=['status'])
                order.status = order_paid
                order.save(update_fields=['status'])
                items.delete()
                messages.success(request, f'Заказ #{order.id} оформлен. Оплата при получении.')
                return redirect('store:order_success', order.id)

        return redirect('store:payment_mock', payment_id=payment.id)

    form = OrderCreateForm(initial={'address': ''})
    return render(request, 'store/order_create.html', {'cart': cart, 'form': form, 'total': total})



@login_required
def order_success_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'store/order_success.html', {'order': order})

@login_required
def order_list(request):
    """
    Список заказов:
    - для обычного пользователя — только свои заказы
    - для менеджера/админа — все заказы
    """
    if request.user.is_staff:
        orders = Order.objects.all().select_related('user', 'status')
    else:
        orders = Order.objects.filter(user=request.user).select_related('status')

    return render(request, 'store/order_list.html', {'orders': orders})

@login_required
def order_detail(request, order_id):
    """
    Детали одного заказа
    """
    order = get_object_or_404(Order, id=order_id)

    if not request.user.is_staff and order.user != request.user:
        messages.error(request, "У вас нет доступа к этому заказу.")
        return redirect('store:order_list')

    items = order.items.select_related('product')
    for item in items:
        item.total_price = item.price * item.quantity

    delivery = getattr(order, 'delivery', None)
    payment = getattr(order, 'payment', None)

    context = {
        'order': order,
        'items': items,
        'delivery': delivery,
        'payment': payment
    }
    return render(request, 'store/order_detail.html', context)

@login_required
def add_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if Review.objects.filter(product=product, user=request.user).exists():
        messages.error(request, "Вы уже оставили отзыв для этого товара.")
        return redirect('store:product_detail', pk=product.id)

    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.user = request.user
            review.save()
            messages.success(request, "Ваш отзыв успешно добавлен!")
            return redirect('store:product_detail', pk=product.id)
    else:
        form = ReviewForm()

    return render(request, 'store/add_review.html', {'product': product, 'form': form})

@staff_member_required
def analytics_dashboard(request):
    # Фильтрация по дате
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    orders = Order.objects.all()

    if start_date:
        orders = orders.filter(order_date__date__gte=start_date)
    if end_date:
        orders = orders.filter(order_date__date__lte=end_date)

    # Основные показатели
    total_orders = orders.count()
    total_revenue = orders.aggregate(Sum('total'))['total__sum'] or 0
    avg_order = orders.aggregate(avg=Sum('total') / Count('id'))['avg'] if total_orders else 0
    unique_users = orders.values('user').distinct().count()

    # Продажи по дням
    sales_by_date = (
        orders.extra({'day': "date(order_date)"})
        .values('day')
        .annotate(total=Sum('total'))
        .order_by('day')
    )

    # Топ товаров
    top_products = (
        OrderItem.objects.filter(order__in=orders)
        .values('product__name')
        .annotate(total_quantity=Sum('quantity'))
        .order_by('-total_quantity')[:5]
    )

    # Заказы по пользователям
    orders_by_user = (
        orders.values('user__username')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )

    context = {
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'avg_order': avg_order,
        'unique_users': unique_users,
        'sales_by_date': list(sales_by_date),
        'top_products': list(top_products),
        'orders_by_user': list(orders_by_user),
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'store/analytics.html', context)

@login_required
@require_POST
def toggle_theme(request):
    """Переключает тему пользователя и сохраняет на сервере"""
    with transaction.atomic():
        settings, _ = UserSettings.objects.get_or_create(user=request.user)
        settings.theme = 'dark' if settings.theme != 'dark' else 'light'
        settings.save(update_fields=['theme'])
    return JsonResponse({'status': 'ok', 'theme': settings.theme})


@login_required
def checkout(request):
    cart = Cart.for_request(request)
    items = CartItem.objects.filter(cart=cart).select_related('product')

    total = sum(i.product.price * i.quantity for i in items)

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            method = form.cleaned_data['payment_method']
            with transaction.atomic():
                order = Order.objects.create(
                    user=request.user,
                    total=total,
                )

                payment = Payment.objects.create(
                    order=order,
                    method=method,
                    amount=total,
                    status=Payment.Status.PENDING,
                )

                if method.code == 'cod':
                    order.status = 'AWAITING_SHIPMENT'
                    order.save(update_fields=['status'])
                    items.delete()
                    return redirect('store:order_success', order_id=order.id)

                return redirect('store:payment_mock', payment_id=payment.id)

    else:
        form = CheckoutForm()

    return render(request, 'store/checkout.html', {
        'items': items,
        'total': total,
        'form': form,
    })

@login_required
def payment_mock(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id)
    if payment.order.user_id != request.user.id and not request.user.is_staff:
        return HttpResponseForbidden("Not your payment")
    return render(request, 'store/payment_mock.html', {'payment': payment})

@require_POST
@login_required
@transaction.atomic
def payment_mock_callback(request, payment_id):
    outcome = request.POST.get('outcome')
    payment = get_object_or_404(Payment.objects.select_for_update(), pk=payment_id)

    if payment.order.user_id != request.user.id and not request.user.is_staff:
        return HttpResponseForbidden("Not your payment")

    p_paid, _ = PaymentStatus.objects.get_or_create(name="Paid")
    p_failed, _ = PaymentStatus.objects.get_or_create(name="Failed")
    s_paid, _ = OrderStatus.objects.get_or_create(name="Paid")
    s_failed, _ = OrderStatus.objects.get_or_create(name="Payment Failed")

    if outcome == 'success':
        payment.status = p_paid
        payment.save(update_fields=['status'])
        payment.order.status = s_paid
        payment.order.save(update_fields=['status'])
        CartItem.objects.filter(cart__user=payment.order.user).delete()
        return redirect('store:order_success', payment.order_id)
    else:
        payment.status = p_failed
        payment.save(update_fields=['status'])
        payment.order.status = s_failed
        payment.order.save(update_fields=['status'])
        return render(request, 'store/payment_failed.html', {'order': payment.order, 'payment': payment})
    

@login_required
@require_POST
def update_page_size(request):
    from .models import UserSettings
    us, _ = UserSettings.objects.get_or_create(user=request.user)
    try:
        ps = max(1, min(100, int(request.POST.get('page_size', 12))))
    except ValueError:
        ps = 12
    us.page_size = ps
    us.save(update_fields=['page_size'])
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))

@login_required
def save_catalog_filters(request):
    from .models import UserSettings
    us, _ = UserSettings.objects.get_or_create(user=request.user)
    data = request.GET.copy()
    data.pop('page', None)
    us.saved_filters['catalog'] = data
    us.save(update_fields=['saved_filters'])
    messages.success(request, "Фильтры сохранены.")
    return redirect('store:product_list')

@login_required
def apply_catalog_filters(request):
    from .models import UserSettings
    us, _ = UserSettings.objects.get_or_create(user=request.user)
    params = us.saved_filters.get('catalog', {})
    if not params:
        messages.info(request, "Сохранённых фильтров нет.")
        return redirect('store:product_list')
    query = urlencode(params, doseq=True)
    return redirect(f"{reverse('store:product_list')}?{query}")

@login_required
def user_settings_view(request):
    us, _ = UserSettings.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = UserSettingsForm(request.POST, instance=us)
        if form.is_valid():
            form.save()
            messages.success(request, "Настройки сохранены.")
            return redirect('store:user_settings')
    else:
        form = UserSettingsForm(instance=us)
    return render(request, 'store/user_settings.html', {'form': form})


@staff_member_required
def download_backup(request, filename):
    path = os.path.join(settings.BASE_DIR, "backups", filename)
    return FileResponse(open(path, "rb"), as_attachment=True)