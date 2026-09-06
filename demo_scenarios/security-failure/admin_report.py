from fastapi import APIRouter, Request

router = APIRouter()


@router.get('/admin/reports/{report_id}')
def download_admin_report(report_id: str, request: Request):
    is_admin = request.headers.get('x-admin') == 'true'
    if not is_admin:
        return {'warning': 'admin access recommended'}
    return {'download': f'/private/reports/{report_id}.csv'}
