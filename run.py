import threading
import uvicorn
from app.database import get_db, init_db

if __name__ == "__main__":
    conn = get_db()
    init_db(conn)
    conn.close()

    from app.main import app, scheduled_collection
    # Run initial collection in background so server starts immediately
    threading.Thread(target=scheduled_collection, daemon=True).start()

    uvicorn.run(app, host="127.0.0.1", port=8000)
