from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    UserRole, OrderStatus, PaymentStatus, DeliveryMethod, DeliveryStatus,
    Genre, PlayerRange, Product, Order, OrderItem, Payment, Delivery, UserProfile, UserSettings
)

User = get_user_model()

class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = '__all__'

class UserProfileSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    role = UserRoleSerializer()

    class Meta:
        model = UserProfile
        fields = ['id', 'user', 'full_name', 'phone', 'role']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    full_name = serializers.CharField(required=False)
    phone = serializers.CharField(required=False)
    role = serializers.SlugRelatedField(
        slug_field='name',
        queryset=UserRole.objects.all(),
        required=False
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'full_name', 'phone', 'role']

    def create(self, validated_data):
        full_name = validated_data.pop('full_name', '')
        phone = validated_data.pop('phone', '')
        role = validated_data.pop('role', None)

        # создаём пользователя
        user = User.objects.create_user(**validated_data)

        # роль по умолчанию
        if not role:
            role, _ = UserRole.objects.get_or_create(name='client')

        # профиль
        UserProfile.objects.create(
            user=user,
            full_name=full_name or user.username,
            phone=phone,
            role=role
        )

        return user


class OrderStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatus
        fields = '__all__'


class PaymentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentStatus
        fields = '__all__'


class DeliveryMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryMethod
        fields = '__all__'


class DeliveryStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryStatus
        fields = '__all__'


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = '__all__'


class PlayerRangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlayerRange
        fields = '__all__'

    def validate(self, data):
        if data['min_players'] > data['max_players']:
            raise serializers.ValidationError("Минимальное количество игроков не может быть больше максимального.")
        return data


class ProductSerializer(serializers.ModelSerializer):
    genre = GenreSerializer(read_only=True)
    genre_id = serializers.PrimaryKeyRelatedField(
        source='genre', queryset=Genre.objects.all(), write_only=True
    )
    player_ranges = PlayerRangeSerializer(many=True, read_only=True)
    player_range_ids = serializers.PrimaryKeyRelatedField(
        many=True, source='player_ranges', queryset=PlayerRange.objects.all(), write_only=True
    )

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'stock',
            'genre', 'genre_id', 'player_ranges', 'player_range_ids'
        ]

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Цена должна быть больше 0.")
        return value

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Количество товара не может быть отрицательным.")
        return value


class UserSerializer(serializers.ModelSerializer):
    role = UserRoleSerializer(read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(
        source='role', queryset=UserRole.objects.all(), write_only=True
    )

    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'phone', 'password_hash', 'role', 'role_id']

    def validate_email(self, value):
        if "@" not in value:
            raise serializers.ValidationError("Некорректный email.")
        return value


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = '__all__'

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Количество товара должно быть больше 0.")
        return value

    def validate(self, data):
        product = data.get("product")
        quantity = data.get("quantity")
        if product and quantity and product.stock < quantity:
            raise serializers.ValidationError(f"Недостаточно товара '{product.name}' на складе.")
        return data


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = ['id', 'user', 'order_date', 'status', 'total', 'items']

    def create(self, validated_data):
        from django.db import transaction

        items_data = validated_data.pop('items')
        with transaction.atomic():
            order = Order.objects.create(**validated_data)
            total = 0
            for item_data in items_data:
                product = item_data['product']
                quantity = item_data['quantity']
                if product.stock < quantity:
                    raise serializers.ValidationError(f"Недостаточно товара {product.name} на складе.")

                product.stock -= quantity
                product.save()

                item_data['order'] = order
                OrderItem.objects.create(**item_data)
                total += item_data['price'] * quantity

            order.total = total
            order.save()
        return order


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'

    def validate(self, data):
        if data['amount'] <= 0:
            raise serializers.ValidationError("Сумма платежа должна быть больше 0.")
        return data


class DeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = Delivery
        fields = '__all__'

class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = ['theme','date_format','number_format','page_size','saved_filters']