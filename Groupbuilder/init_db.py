
from Groupbuilder.app import db, app

with app.app_context():
    db.create_all()
    print("✅ Datenbanktabellen wurden erstellt.")
