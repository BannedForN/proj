from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Sum, Count
from django.http import HttpResponse
from django.contrib import messages
from django.db import transaction
from django.views.generic import ListView, DetailView

from rest_framework import viewsets, status, generics, permissions
from rest_framework.response import Response
from rest_framework.decorators import action

from .models import (
    UserRole, OrderStatus, PaymentStatus, DeliveryMethod, DeliveryStatus,
    Genre, PlayerRange, Product, Order, OrderItem, Payment, Delivery,
    UserProfile, Cart, CartItem, Review
)
from .serializers import (
    UserRoleSerializer, OrderStatusSerializer, PaymentStatusSerializer,
    DeliveryMethodSerializer, DeliveryStatusSerializer, GenreSerializer,
    PlayerRangeSerializer, UserSerializer, ProductSerializer,
    OrderItemSerializer, OrderSerializer, PaymentSerializer,
    DeliverySerializer, UserProfileSerializer, RegisterSerializer
)
from .permissions import IsAdmin, IsManagerOrAdmin, IsClientOrReadOnly
from .forms import RegisterForm, LoginForm, ReviewForm
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        products = context['products']
        # Подсчёт среднего рейтинга для каждой игры
        for product in products:
            avg = product.reviews.aggregate(average=Avg('rating'))['average'] or 0
            product.avg_rating = avg
            product.review_count = product.reviews.count()
        return context


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
            user = form.save()
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
    if not cart.items.exists():
        messages.error(request, "Ваша корзина пуста.")
        return redirect('store:product_list')

    if request.method == 'POST':
        address = request.POST.get('address')
        if not address:
            messages.error(request, "Введите адрес доставки.")
            return redirect('store:cart_detail')

        with transaction.atomic():
            status_new, _ = OrderStatus.objects.get_or_create(name="New")
            order = Order.objects.create(
                user=request.user,
                status=status_new,
                total=cart.total_price()
            )

            for item in cart.items.select_related('product'):
                if item.product.stock < item.quantity:
                    messages.error(request, f"Недостаточно товара: {item.product.name}")
                    raise transaction.TransactionManagementError()
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )
                item.product.stock -= item.quantity
                item.product.save()

            delivery_status, _ = DeliveryStatus.objects.get_or_create(name="Pending")
            delivery_method, _ = DeliveryMethod.objects.get_or_create(name="Standard")
            Delivery.objects.create(
                order=order,
                address=address,
                method=delivery_method,
                status=delivery_status
            )

            payment_status, _ = PaymentStatus.objects.get_or_create(name="Pending")
            Payment.objects.create(
                order=order,
                amount=order.total,
                status=payment_status
            )

            cart.items.all().delete()

        messages.success(request, f'Заказ #{order.id} успешно оформлен.')
        return redirect('store:order_success', order.id)

    return render(request, 'store/order_create.html', {'cart': cart})



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

    # Проверка доступа: обычный пользователь видит только свои заказы
    if not request.user.is_staff and order.user != request.user:
        messages.error(request, "У вас нет доступа к этому заказу.")
        return redirect('store:order_list')

    items = order.items.select_related('product')
    for item in items:
        item.total_price = item.price * item.quantity  # добавляем атрибут total_price

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

    # Проверка: пользователь уже оставил отзыв
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