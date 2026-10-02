from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .dto.product import ProcessOrderResponse
from .services.implementations.product_service import ps
from .services.process_order import OrderNotFound, ProcessOrderUseCase


@csrf_exempt
@require_POST
def process_order(request, order_id):
    try:
        processed_id = ProcessOrderUseCase(policy=ps).execute(order_id)
    except OrderNotFound:
        return JsonResponse({'error': 'order not found'}, status=404)

    return JsonResponse({'id': ProcessOrderResponse(processed_id).get_id()}, status=200)
