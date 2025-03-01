# Flask Web App Development Guide

## Development Commands
- Run app: `python app.py` (starts development server with debug=True)
- Install dependencies: `pip install -r requirements.txt`
- Create new virtual environment: `python -m venv venv`
- Activate virtual environment: `. venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)

## Code Style Guidelines
- Imports: Group standard library, third-party, and local imports with a blank line between groups
- Line length: Maximum 88 characters (PEP 8)
- Indentation: 4 spaces
- Naming: 
  - Classes: PascalCase (e.g., `User`, `PostLike`)
  - Functions/methods: snake_case (e.g., `is_logged_in`, `show_establishment`)
  - Variables: snake_case (e.g., `user_id`, `existing_like`)
- Error handling: Use Flask's error handlers for HTTP errors, explicit validation for form data
- Comments: Use docstrings for routes and functions, section headers with dashed lines for organization
- Database: Use SQLAlchemy models with explicit relationships and constraints

## Project Structure
- `app.py`: Main application file with models and routes
- `templates/`: HTML templates using Jinja2
- `static/`: CSS, JavaScript, images
- `site_data.db`: SQLite database