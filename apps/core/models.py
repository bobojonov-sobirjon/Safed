"""
Base models with common functionality:
- Soft delete
- Audit fields (created_by, updated_by)
- Timestamps
"""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING
from django.db import models
from django.db.models import QuerySet
from django.utils import timezone

if TYPE_CHECKING:
    from apps.accounts.models import CustomUser


class SoftDeleteManager(models.Manager):
    """Manager that filters out soft-deleted objects by default."""
    
    def get_queryset(self) -> QuerySet:
        return super().get_queryset().filter(is_deleted=False)
    
    def all_with_deleted(self) -> QuerySet:
        """Return all objects including deleted ones."""
        return super().get_queryset()
    
    def deleted_only(self) -> QuerySet:
        """Return only deleted objects."""
        return super().get_queryset().filter(is_deleted=True)


class TimeStampedModel(models.Model):
    """Abstract base model with timestamp fields."""
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    
    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """Abstract base model with soft delete functionality."""
    
    is_deleted = models.BooleanField(
        default=False,
        verbose_name='Удалён',
        db_index=True
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата удаления'
    )
    
    objects = SoftDeleteManager()
    all_objects = models.Manager()
    
    class Meta:
        abstract = True
    
    def delete(self, using=None, keep_parents=False, hard_delete=False):
        """Soft delete by default, hard delete if specified."""
        if hard_delete:
            return super().delete(using=using, keep_parents=keep_parents)
        
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])
    
    def restore(self):
        """Restore a soft-deleted object."""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])
    
    def hard_delete(self):
        """Permanently delete the object."""
        return super().delete()


class AuditModel(models.Model):
    """Abstract base model with audit fields."""
    
    created_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created',
        verbose_name='Создал'
    )
    updated_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_updated',
        verbose_name='Обновил'
    )
    
    class Meta:
        abstract = True


class BaseModel(TimeStampedModel, SoftDeleteModel):
    """
    Base model combining timestamps and soft delete.
    Use this for most models.
    """
    
    class Meta:
        abstract = True


class FullAuditModel(TimeStampedModel, SoftDeleteModel, AuditModel):
    """
    Full audit model with timestamps, soft delete, and audit fields.
    Use this for important business models.
    """
    
    class Meta:
        abstract = True
