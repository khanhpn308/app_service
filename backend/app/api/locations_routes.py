import os
from fastapi import APIRouter, Depends
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix='/locations', tags=['locations'])

def get_floorplan_dir():
    # 1. From environment variable
    env_path = os.getenv('FLOORPLAN_DIR')
    if env_path and os.path.exists(env_path):
        return os.path.abspath(env_path)
    
    # 2. Absolute path based on this file (for local development)
    # app_service/backend/app/api/locations_routes.py -> app_service/src/assets/floorplans
    try:
        current_file = os.path.abspath(__file__)
        api_dir = os.path.dirname(current_file)
        app_dir = os.path.dirname(api_dir)
        backend_dir = os.path.dirname(app_dir)
        
        path1 = os.path.abspath(os.path.join(backend_dir, '..', 'src', 'assets', 'floorplans'))
        if os.path.exists(path1):
            return path1
            
        # 3. For Docker environment (if mounted or structured differently)
        # Try relative to CWD
        path2 = os.path.abspath(os.path.join(os.getcwd(), '..', 'src', 'assets', 'floorplans'))
        if os.path.exists(path2):
            return path2
            
        return path1 # Default fallback
    except Exception:
        return "../src/assets/floorplans"

@router.get('')
def get_locations(user: User = Depends(get_current_user)):
    try:
        target_dir = get_floorplan_dir()
        if not target_dir or not os.path.exists(target_dir):
            # Không lộ đường dẫn filesystem/cwd ra client (information disclosure).
            return {'data': [], 'error': 'Directory not found'}

        files = os.listdir(target_dir)
        # Case-insensitive .webp check only
        locations = sorted({os.path.splitext(f)[0] for f in files if f.lower().endswith('.webp')})

        return {'data': sorted(locations)}
    except Exception:
        # Nuốt chi tiết exception khỏi response; ghi log phía server thay vì trả str(e).
        import logging
        logging.getLogger('uvicorn.error').exception('get_locations failed')
        return {'data': [], 'error': 'Internal error'}
