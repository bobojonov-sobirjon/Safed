"""
User and authentication models.
"""
from __future__ import annotations
from typing import Optional
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.utils import timezone
from datetime import timedelta

from apps.accounts.managers.user_manager import CustomUserManager
from apps.core.enums import DeviceType


class CustomUser(AbstractUser):
    """Custom user model with phone-based authentication."""
    
    groups = models.ManyToManyField(
        Group,
        related_name='customuser_set',
        blank=True,
        verbose_name='Группы',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='customuser_set',
        blank=True,
        verbose_name='Права пользователя',
    )
    phone = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name='Телефон',
        db_index=True
    )
    is_verified = models.BooleanField(
        default=False,
        verbose_name='Подтвержден',
        db_index=True
    )
    is_admin = models.BooleanField(
        default=False,
        verbose_name='Администратор'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    
    objects = CustomUserManager()

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['is_verified']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self) -> str:
        return self.phone or self.username or f'User {self.pk}'
    
    @property
    def full_name(self) -> str:
        return f'{self.first_name} {self.last_name}'.strip() or self.phone or ''
    
    def is_in_group(self, group_name: str) -> bool:
        """Check if user belongs to a specific group."""
        return self.groups.filter(name=group_name).exists()
    
    def is_staff_member(self) -> bool:
        """Check if user is in any staff group."""
        from apps.core.enums import UserGroup
        return self.groups.filter(name__in=UserGroup.staff_groups()).exists()


class PhoneOTP(models.Model):
    """Phone OTP for verification."""
    
    phone = models.CharField(
        max_length=20,
        verbose_name='Телефон',
        db_index=True
    )
    code = models.CharField(
        max_length=6,
        verbose_name='Код'
    )
    is_verified = models.BooleanField(
        default=False,
        verbose_name='Подтвержден'
    )
    attempts = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Попытки'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    OTP_EXPIRY_MINUTES = 2
    MAX_ATTEMPTS = 3

    class Meta:
        verbose_name = 'Phone OTP'
        verbose_name_plural = 'Phone OTPs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone', 'code']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self) -> str:
        return f'{self.phone} - {self.code}'

    def is_expired(self) -> bool:
        """Check if OTP is expired."""
        return timezone.now() > self.created_at + timedelta(minutes=self.OTP_EXPIRY_MINUTES)
    
    def is_valid(self, code: str) -> bool:
        """Check if OTP is valid."""
        if self.is_expired():
            return False
        if self.attempts >= self.MAX_ATTEMPTS:
            return False
        return self.code == code
    
    def increment_attempts(self):
        """Increment failed attempts counter."""
        self.attempts += 1
        self.save(update_fields=['attempts'])


class UserDevice(models.Model):
    """User device for push notifications."""
    
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='devices',
        verbose_name='Пользователь',
    )
    device_token = models.CharField(
        max_length=512,
        verbose_name='Token устройства'
    )
    device_type = models.CharField(
        max_length=20,
        choices=DeviceType.choices(),
        verbose_name='Тип устройства'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен',
        db_index=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    class Meta:
        verbose_name = 'Устройство пользователя'
        verbose_name_plural = 'Устройства пользователей'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['device_token']),
        ]
        unique_together = [['user', 'device_token']]

    def __str__(self) -> str:
        return f'{self.device_type} - {self.user_id}'
