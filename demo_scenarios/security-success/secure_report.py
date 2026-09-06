from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from demo_security import CurrentUser, require_authenticated_user

router = APIRouter()
REPORT_ROOT = Path('/srv/reports').resolve()


@router.get('/admin/reports/{report_id}')
def download_admin_report(
    report_id: int,
    user: CurrentUser = Depends(require_authenticated_user),
):
    if 'admin' not in user.roles:
        raise HTTPException(status_code=403, detail='Administrator access required')

    report_path = (REPORT_ROOT / f'{report_id}.csv').resolve()
    if REPORT_ROOT not in report_path.parents:
        raise HTTPException(status_code=400, detail='Invalid report identifier')
    if not report_path.is_file():
        raise HTTPException(status_code=404, detail='Report not found')

    return {'report_id': report_id, 'requested_by': user.user_id}
