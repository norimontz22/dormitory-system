# Haven: Dormitory and Housing Management System

Flask (Python) back end, SQLite database, HTML/CSS/JavaScript front end.

## How to run
1. Put `app.py`, `index.html` and `requirements.txt` in the SAME folder (no `static` folder needed).
2. In a terminal inside that folder: `pip install -r requirements.txt`
3. Run: `python app.py`
4. Open http://127.0.0.1:5001
5. Log in with `admin` / `admin123` or `staff` / `staff123`.

On the first run the database (`dormhub.db`) is created with fictional demo data:
60 rooms in 3 buildings, 150 residents (110 living in, 40 moved out), rent payments and 40 repair requests.
All names, numbers and emails are made up. There are no students and no barangays.

## Rule enforced by the server
A room cannot take more residents than it has beds, and a resident cannot have two active stays.
