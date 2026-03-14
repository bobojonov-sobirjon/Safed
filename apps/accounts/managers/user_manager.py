from django.contrib.auth.models import BaseUserManager
from django.db import models


class CustomUserManager(BaseUserManager):
    """Base manager for CustomUser with all necessary methods"""
    
    def create_user(self, phone, password=None, **extra_fields):
        """Create and save a regular User"""
        if not phone:
            raise ValueError('Phone обязателен')
        username = extra_fields.pop('username', None) or phone
        user = self.model(phone=phone, username=username, **extra_fields)
        if password:
            user.set_password(password)
        user.save()
        return user
    
    def create_superuser(self, phone, password=None, **extra_fields):
        """Create and save a SuperUser"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(phone, password, **extra_fields)
