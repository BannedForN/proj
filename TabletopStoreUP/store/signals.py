from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile, UserRole


@receiver(post_migrate)
def create_default_roles(sender, **kwargs):
    """Создаёт роли после миграций"""
    if sender.label != 'store':  # замени 'store' на имя твоего приложения
        return

    roles = ['guest', 'client', 'manager', 'admin']
    for name in roles:
        UserRole.objects.get_or_create(name=name)


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """Создаёт или обновляет профиль при изменении пользователя"""
    # Определяем роль
    role_name = "admin" if instance.is_superuser else "client"
    role, _ = UserRole.objects.get_or_create(name=role_name)

    # Проверяем, есть ли профиль
    profile, profile_created = UserProfile.objects.get_or_create(
        user=instance,
        defaults={
            'full_name': instance.username,
            'role': role
        }
    )

    # Если профиль уже был, но роль изменилась — обновим
    if not profile_created and profile.role != role:
        profile.role = role
        profile.save(update_fields=['role'])

    print(f"✅ Профиль {instance.username}: {role_name}")
