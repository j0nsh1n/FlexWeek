//! The account and save rules the local FastAPI server holds today (`backend/app.py`'s helpers, request
//! checks and route bodies), as plain Rust calls with no HTTP: sign up and in, weeks, homework and plans,
//! preferences, routines, restore points, export and import. It calls `flexweek-store` and
//! `flexweek-engine`; the time and randomness come in as arguments (2.0.0 plan, phase P1).
