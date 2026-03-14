"""
News/Posts models.
"""
from __future__ import annotations
from django.db import models
from django.urls import reverse
from parler.models import TranslatableModel, TranslatedFields

from apps.core.models import BaseModel


class PostManager(models.Manager):
    """Custom manager for Post."""
    
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)
    
    def active(self):
        """Get active posts."""
        return self.get_queryset().filter(is_active=True)
    
    def with_images(self):
        """Prefetch images."""
        return self.get_queryset().prefetch_related('images')


class Post(TranslatableModel):
    """News post with translations."""
    
    translations = TranslatedFields(
        title=models.CharField(
            max_length=255,
            verbose_name='Заголовок',
            null=True,
            blank=True
        ),
        content=models.TextField(
            verbose_name='Контент',
            null=True,
            blank=True
        ),
        short_description=models.TextField(
            verbose_name='Краткое описание',
            null=True,
            blank=True,
            max_length=500
        ),
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активный',
        db_index=True
    )
    is_deleted = models.BooleanField(
        default=False,
        verbose_name='Удалён',
        db_index=True
    )
    views_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Просмотры'
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата публикации'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    
    objects = PostManager()

    class Meta:
        verbose_name = 'Пост'
        verbose_name_plural = 'Посты'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'is_deleted']),
            models.Index(fields=['created_at']),
            models.Index(fields=['published_at']),
        ]

    def __str__(self) -> str:
        return self.safe_translation_getter('title', default=f'Post {self.pk}')
    
    def get_absolute_url(self) -> str:
        return reverse('post_detail', kwargs={'pk': self.pk})
    
    def increment_views(self):
        """Increment view counter."""
        self.__class__.objects.filter(pk=self.pk).update(
            views_count=models.F('views_count') + 1
        )


# Backward compatibility alias
Posts = Post


class PostImage(BaseModel):
    """Post image."""
    
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='Пост'
    )
    image = models.ImageField(
        upload_to='posts/images/',
        verbose_name='Изображение'
    )
    caption = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Подпись'
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Порядок'
    )

    class Meta:
        verbose_name = 'Изображение поста'
        verbose_name_plural = 'Изображения поста'
        ordering = ['order', '-created_at']
        indexes = [
            models.Index(fields=['post']),
        ]

    def __str__(self) -> str:
        return f'Изображение #{self.pk}'


# Backward compatibility alias
PostImages = PostImage
