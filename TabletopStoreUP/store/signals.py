from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile, UserRole, UserSettings


@receiver(post_migrate)
def create_default_roles(sender, **kwargs):
    if getattr(sender, "label", None) != 'store':
        return
    for name in ['guest', 'client', 'manager', 'admin']:
        UserRole.objects.get_or_create(name=name)

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    role_name = "admin" if instance.is_superuser else "client"
    role, _ = UserRole.objects.get_or_create(name=role_name)
    profile, created_profile = UserProfile.objects.get_or_create(
        user=instance,
        defaults={'full_name': instance.username, 'role': role}
    )
    if not created_profile and profile.role != role:
        profile.role = role
        profile.save(update_fields=['role'])

@receiver(post_save, sender=User)
def create_user_settings(sender, instance, created, **kwargs):
    if created:
        UserSettings.objects.get_or_create(user=instance)