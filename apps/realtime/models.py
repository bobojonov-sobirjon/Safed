from django.db import models
from django.conf import settings

from apps.orders.models import Order


class ChatRoom(models.Model):
    """Chat room for order communication between customer and staff."""
    
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='chat_room',
        verbose_name='Заказ',
    )
    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='initiated_chats',
        verbose_name='Инициатор',
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_chats',
        verbose_name='Получатель',
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен'
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
        verbose_name = 'Чат комната'
        verbose_name_plural = 'Чат комнаты'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['initiator']),
            models.Index(fields=['receiver']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f'ChatRoom #{self.id} (Order #{self.order_id})'
    
    @property
    def participants(self):
        """Return list of participants."""
        participants = [self.initiator]
        if self.receiver:
            participants.append(self.receiver)
        return participants
    
    def is_participant(self, user):
        """Check if user is a participant."""
        if not user or not hasattr(user, 'id'):
            return False
        return user.id == self.initiator_id or user.id == self.receiver_id


class ChatMessage(models.Model):
    """Message in a chat room."""
    
    room = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='Комната',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        verbose_name='Отправитель',
    )
    message = models.TextField(
        verbose_name='Сообщение'
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name='Прочитано'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Сообщение чата'
        verbose_name_plural = 'Сообщения чата'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['room']),
            models.Index(fields=['sender']),
            models.Index(fields=['is_read']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'Message #{self.id} in Room #{self.room_id}'


class Notification(models.Model):
    """User notification."""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='Пользователь',
    )
    title = models.CharField(
        max_length=255,
        verbose_name='Заголовок'
    )
    body = models.TextField(
        verbose_name='Текст'
    )
    type = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Тип'
    )
    data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Дополнительные данные'
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name='Прочитано'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

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
