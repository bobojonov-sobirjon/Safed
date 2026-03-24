"""
Category models with MPTT-like optimization.
"""
from __future__ import annotations
from typing import List, Optional
from django.db import models
from django.db.models import QuerySet
from parler.models import TranslatableModel, TranslatedFields

from apps.core.models import BaseModel


class CategoryManager(models.Manager):
    """Custom manager for Category with tree operations."""
    
    def get_queryset(self) -> QuerySet:
        return super().get_queryset().filter(is_deleted=False)
    
    def roots(self) -> QuerySet:
        """Get root categories (no parent)."""
        return self.get_queryset().filter(parent__isnull=True)
    
    def active(self) -> QuerySet:
        """Get active categories."""
        return self.get_queryset().filter(is_active=True)
    
    def with_children(self) -> QuerySet:
        """Prefetch children."""
        return self.get_queryset().prefetch_related('children')


class Category(TranslatableModel):
    """Category model with hierarchical structure."""
    
    translations = TranslatedFields(
        name=models.CharField(
            max_length=255,
            verbose_name='Название категории',
            null=True,
            blank=True
        ),
    )
    home_order = models.PositiveIntegerField(
        default=0,
        verbose_name='Порядок на главной странице',
        db_index=True, null=True, blank=True
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='Родительская категория'
    )
    icon = models.ImageField(
        upload_to='categories/icons/',
        null=True,
        blank=True,
        verbose_name='Иконка категории'
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активная категория',
        db_index=True
    )
    is_deleted = models.BooleanField(
        default=False,
        verbose_name='Удалена',
        db_index=True
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name='Порядок категории',
        db_index=True
    )
    level = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Уровень вложенности',
        editable=False
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    objects = CategoryManager()

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['order', 'level']
        indexes = [
            models.Index(fields=['parent', 'is_active']),
            models.Index(fields=['order']),
            models.Index(fields=['level']),
        ]

    def __str__(self) -> str:
        return self.safe_translation_getter('name', default=f'Category {self.pk}')
    
    def save(self, *args, **kwargs):
        self.level = self._calculate_level()
        super().save(*args, **kwargs)
    
    def _calculate_level(self) -> int:
        """Calculate nesting level."""
        level = 0
        parent = self.parent
        while parent:
            level += 1
            parent = parent.parent
        return level
    
    def get_ancestors(self) -> List['Category']:
        """Get all ancestor categories."""
        ancestors = []
        parent = self.parent
        while parent:
            ancestors.insert(0, parent)
            parent = parent.parent
        return ancestors
    
    def get_descendants(self) -> QuerySet:
        """Get all descendant categories (recursive)."""
        descendants = list(self.children.filter(is_deleted=False))
        for child in list(descendants):
            descendants.extend(child.get_descendants())
        return descendants
    
    def get_all_descendant_ids(self) -> List[int]:
        """Get IDs of all descendants including self."""
        ids = [self.id]
        for child in self.children.filter(is_deleted=False, is_active=True):
            ids.extend(child.get_all_descendant_ids())
        return ids
    
    @property
    def is_root(self) -> bool:
        """Check if this is a root category."""
        return self.parent is None
    
    @property
    def is_leaf(self) -> bool:
        """Check if this is a leaf category (no children)."""
        return not self.children.filter(is_deleted=False).exists()
    
    @property
    def full_path(self) -> str:
        """Get full category path (e.g., 'Electronics > Phones > Smartphones')."""
        ancestors = self.get_ancestors()
        names = [c.name for c in ancestors] + [self.name]
        return ' > '.join(filter(None, names))
