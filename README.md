# Beautician Booking API

# # A FastAPI application for managing beautician bookings, including user signup/login, beautician management, booking workflow, and admin controls.

# # Features
User signup and login with JWT authentication
Beautician management (create, list)
Booking workflow with Redis-based locking
Booking status updates with validation
Admin view for all bookings
Proper role-based access control (user vs beautician)

# # Installation
Clone the repository:
git clone https://github.com/yourusername/beautician-booking.git
cd beautician-booking
Create a virtual environment and activate it:
python -m venv venv
source venv/bin/activate   # Linux / macOS
venv\Scripts\activate      # Windows

# # Install dependencies:
pip install -r requirements.txt
Run the application:
uvicorn main:app --reload

# #  The API will be available at http://127.0.0.1:8000/.

# # API Endpoints
```
Authentication
Method	Endpoint	Body / Params	Description
POST	/signup	JSON { "email": "...", "password": "...", "role": "...", "location": "..." }	Create a new user
POST	/login	Form URL Encoded { username, password }	Get JWT access token
Beautician Management
Method	Endpoint	Body	Auth	Description
POST	/beautician	JSON { "name": "Alice", "location": "City B" }	Bearer token	Create a beautician (beautician role only)
Booking Workflow
Method	Endpoint	Body / Params	Auth	Description
POST	/booking	None	Bearer token	Create a booking (assign available beautician)
PUT	/booking/{id}/accept	None	Bearer token	Accept a booking (beautician only)
PUT	/booking/{id}/status	Query param status=Completed	Bearer token	Update booking status (user or beautician)
```
```
# Note on booking status transitions:

Requested -> Accepted / Cancelled
Accepted -> In Progress / Cancelled
In Progress -> Completed

Invalid transitions will return an error like:

{
  "detail": "Invalid transition from Completed to Accepted"
}
```

# # Admin Endpoints
Method	Endpoint	Query Params	Auth	Description
GET	/admin/bookings	status (optional)	Bearer token	View all bookings (filter by status if needed)

```
Example:

curl -X GET "http://127.0.0.1:8000/admin/bookings?status=Completed" \
-H "Authorization: Bearer <access_token>" \
-H "accept: application/json"
Example Workflow
Create a beautician:
POST /beautician
{
  "name": "Alice",
  "location": "City B"
}
Book a beautician:
POST /booking

Response:

{
  "id": 1,
  "user_id": 1,
  "beautician_id": 1,
  "status": "Requested"
}
Accept booking (beautician):
PUT /booking/1/accept
Update status to Completed:
PUT /booking/1/status?status=Completed
Admin view completed bookings:
GET /admin/bookings?status=Completed
```

# # Dependencies
FastAPI
SQLAlchemy
Uvicorn
Redis (for locking)
Passlib (for password hashing)
Python-Jose (for JWT)
Project Structure
.
```
├── main.py           # FastAPI app with routes
├── models.py         # SQLAlchemy models
├── schemas.py        # Pydantic schemas
├── crud.py           # Database CRUD operations
├── auth.py           # Authentication & JWT
├── database.py       # DB connection
├── redis_conn.py     # Redis client
├── requirements.txt  # Python dependencies
└── README.md         # Project README
```
