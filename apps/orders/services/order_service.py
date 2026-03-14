"""
Order business logic service.
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
from django.db import transaction
from django.db.models import F, Sum

from apps.orders.models import Order, OrderProduct, OrderCourier
from apps.products.models import Products
from apps.accounts.models import CustomUser
from apps.core.enums import OrderStatus, UserGroup


class OrderServiceError(Exception):
    """Custom exception for order service errors."""
    pass


class InsufficientStockError(OrderServiceError):
    """Raised when there's not enough stock."""
    def __init__(self, products: List[Dict]):
        self.products = products
        super().__init__('Insufficient stock')


class OrderService:
    """Service class for order operations."""
    
    @staticmethod
    @transaction.atomic
    def create_order(
        user: CustomUser,
        products_data: List[Dict[str, Any]],
        lat: Optional[Decimal] = None,
        long: Optional[Decimal] = None,
        address: str = ''
    ) -> Order:
        """
        Create a new order with products.
        
        Args:
            user: The user placing the order
            products_data: List of dicts with product_id, quantity, total_price
            lat: Latitude
            long: Longitude
            address: Delivery address
            
        Returns:
            Created Order instance
            
        Raises:
            InsufficientStockError: If any product has insufficient stock
        """
        product_ids = [item['product_id'] for item in products_data]
        products = {
            p.id: p 
            for p in Products.objects.select_for_update().filter(id__in=product_ids)
        }
        
        insufficient = []
        for item in products_data:
            product = products.get(item['product_id'])
            if not product:
                continue
            if product.quantity < item['quantity']:
                insufficient.append({
                    'product_id': product.id,
                    'available_quantity': product.quantity,
                    'requested_quantity': item['quantity'],
                })
        
        if insufficient:
            raise InsufficientStockError(insufficient)
        
        total_amount = sum(
            Decimal(str(item['total_price'])) 
            for item in products_data
        )
        
        order = Order.objects.create(
            user=user,
            lat=lat,
            long=long,
            address=address,
            status=OrderStatus.PENDING.value,
            total_amount=total_amount,
        )
        
        order_products = [
            OrderProduct(
                order=order,
                product_id=item['product_id'],
                quantity=item['quantity'],
                unit_price=products[item['product_id']].current_price,
                total_price=item['total_price'],
            )
            for item in products_data
        ]
        OrderProduct.objects.bulk_create(order_products)
        
        return order
    
    @staticmethod
    @transaction.atomic
    def update_order(
        order: Order,
        products_data: Optional[List[Dict[str, Any]]] = None,
        lat: Optional[Decimal] = None,
        long: Optional[Decimal] = None,
        address: Optional[str] = None
    ) -> Order:
        """Update an existing order."""
        if not order.can_update_or_delete:
            raise OrderServiceError('Обновление возможно только при статусе pending')
        
        if lat is not None:
            order.lat = lat
        if long is not None:
            order.long = long
        if address is not None:
            order.address = address
        
        if products_data is not None:
            product_ids = [item['product_id'] for item in products_data]
            products = {
                p.id: p 
                for p in Products.objects.select_for_update().filter(id__in=product_ids)
            }
            
            insufficient = []
            for item in products_data:
                product = products.get(item['product_id'])
                if product and product.quantity < item['quantity']:
                    insufficient.append({
                        'product_id': product.id,
                        'available_quantity': product.quantity,
                        'requested_quantity': item['quantity'],
                    })
            
            if insufficient:
                raise InsufficientStockError(insufficient)
            
            order.order_products.all().delete()
            
            order_products = [
                OrderProduct(
                    order=order,
                    product_id=item['product_id'],
                    quantity=item['quantity'],
                    unit_price=products[item['product_id']].current_price,
                    total_price=item['total_price'],
                )
                for item in products_data
            ]
            OrderProduct.objects.bulk_create(order_products)
            
            order.total_amount = sum(
                Decimal(str(item['total_price'])) 
                for item in products_data
            )
        
        order.save()
        return order
    
    @staticmethod
    @transaction.atomic
    def change_status(order: Order, new_status: str) -> Order:
        """
        Change order status with side effects.
        
        When completing an order, decrements product quantities.
        """
        if new_status == OrderStatus.COMPLETED.value:
            for op in order.order_products.select_related('product'):
                if op.product:
                    Products.objects.filter(id=op.product_id).update(
                        quantity=F('quantity') - op.quantity
                    )
        
        order.status = new_status
        order.save(update_fields=['status', 'updated_at'])
        return order
    
    @staticmethod
    @transaction.atomic
    def assign_courier(order: Order, courier: CustomUser) -> OrderCourier:
        """Assign a courier to an order."""
        if not order.can_add_courier:
            raise OrderServiceError('Назначение курьера возможно только при статусе process')
        
        if not courier.is_in_group(UserGroup.COURIER.value):
            raise OrderServiceError('Пользователь не является курьером')
        
        order_courier, created = OrderCourier.objects.get_or_create(
            order=order,
            courier=courier,
        )
        
        order.status = OrderStatus.DELIVERING.value
        order.save(update_fields=['status', 'updated_at'])
        
        return order_courier
    
    @staticmethod
    def get_order_statistics(
        date_from=None,
        date_to=None
    ) -> Dict[str, Any]:
        """Get order statistics for admin dashboard."""
        from django.db.models import Count
        
        orders_qs = Order.objects.filter(is_deleted=False)
        
        if date_from:
            orders_qs = orders_qs.filter(created_at__date__gte=date_from)
        if date_to:
            orders_qs = orders_qs.filter(created_at__date__lte=date_to)
        
        total_orders = orders_qs.count()
        orders_by_status = list(
            orders_qs.values('status').annotate(count=Count('id')).order_by('status')
        )
        total_customers = orders_qs.values('user').distinct().count()
        
        completed_orders = orders_qs.filter(status=OrderStatus.COMPLETED.value)
        total_revenue = completed_orders.aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0.00')
        
        return {
            'total_orders': total_orders,
            'total_customers': total_customers,
            'total_revenue': total_revenue,
            'orders_by_status': orders_by_status,
        }
