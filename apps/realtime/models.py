from django.db import models
from django.conf import settings

from apps.orders.models import Order


class ChatMessage(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='chat_messages',
        verbose_name='Заказ',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        verbose_name='Отправитель',
    )
    message = models.TextField(verbose_name='Сообщение')
    is_read = models.BooleanField(default=False, verbose_name='Прочитано')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        verbose_name = 'Сообщение чата'
        verbose_name_plural = 'Сообщения чата'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['sender']),
            models.Index(fields=['is_read']),
        ]

    def __str__(self):
        return f'ChatMessage #{self.id} (order {self.order_id})'


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='Пользователь',
    )
    title = models.CharField(max_length=255, verbose_name='Заголовок')
    body = models.TextField(verbose_name='Текст')
    type = models.CharField(max_length=50, blank=True, verbose_name='Тип')
    is_read = models.BooleanField(default=False, verbose_name='Прочитано')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['is_read']),
            models.Index(fields=['type']),
        ]

    def __str__(self):
        return f'Notification #{self.id} ({self.user_id})'

