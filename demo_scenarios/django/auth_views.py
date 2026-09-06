from django.http import JsonResponse

from .models import CustomerRecord


def customer_record(request, record_id: int):
    record = CustomerRecord.objects.get(pk=record_id)
    return JsonResponse({
        'id': record.id,
        'email': record.email,
        'notes': record.internal_notes,
    })

